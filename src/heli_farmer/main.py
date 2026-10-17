import argparse
import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from heli_farmer import detectors
from heli_farmer.capture import ScreenCapture
from heli_farmer.config import load_config
from heli_farmer.crate_loop import STEPS, CrateLoop, LeaveLayer, StepFailed
from heli_farmer.detectors import Vision
from heli_farmer.inputs import Input
from heli_farmer.killswitch import Killswitch, Stopped, wait
from heli_farmer.logs import save_debug_screenshot, setup_logging
from heli_farmer.states import (
    Detectors,
    Layer,
    RoundOver,
    SafeStop,
    StateMachine,
    UnknownStateTimeout,
    Watchdog,
    not_built,
)
from heli_farmer.window import foreground_title, is_foreground

log = logging.getLogger(__name__)

EXIT_STOPPED = 0
EXIT_ERROR = 1
EXIT_UNKNOWN_STATE = 2
EXIT_SAFE_STOP = 3


class Finished(Exception):
    pass


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="heli-farmer")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="keine Eingaben senden, nur loggen")
    parser.add_argument("--hold-test", action="store_true", help="hält eine Taste bis zum Stopp")
    parser.add_argument("--layer", type=int, choices=[1], help="nur bis zu diesem Layer arbeiten")
    parser.add_argument("--once", action="store_true", help="genau eine Runde")
    parser.add_argument("--step", choices=STEPS, help="nur diesen einen Schritt")
    parser.add_argument("--map", default="default", help="Kartenname für Parameter aus maps")
    args = parser.parse_args(argv)
    if (args.once or args.step) and args.layer is None:
        parser.error("--once und --step brauchen --layer 1")
    return args


def countdown(stop: threading.Event, seconds: int) -> None:
    for left in range(seconds, 0, -1):
        log.info("Start in %d s: jetzt ins Spiel wechseln", left)
        wait(stop, 1)


def hold_test(inp: Input, stop: threading.Event, key: str, repeat_s: float) -> None:
    log.info("Hold-Test: halte '%s' gedrückt", key)
    while True:
        inp.key_down(key)
        wait(stop, repeat_s)


def build_machine(
    config: dict, args: argparse.Namespace, vision: Vision, loop: CrateLoop, inp: Input
) -> StateMachine:
    def unknown(frame) -> None:
        inp.release_all()
        if vision.round_over(frame):
            raise RoundOver

    handlers = {Layer.UNKNOWN: unknown}
    if args.layer == 1:
        steps = (args.step,) if args.step else ()

        def crate_loop(frame) -> None:
            loop.run(steps, args.once)
            if steps or args.once:
                raise Finished

        def assumed(frame) -> bool:
            return True

        found = Detectors(on_server=assumed, in_team_blue=assumed, has_heli=vision.has_heli)
        handlers[Layer.CRATE_LOOP] = crate_loop
        for layer in (Layer.VEHICLE, Layer.TEAM, Layer.SERVER):
            handlers[layer] = not_built(layer)
    else:
        found = Detectors(detectors.on_server, detectors.in_team_blue, vision.has_heli)
    return StateMachine(found, handlers, Watchdog(config["timeouts"]["unknown_state_s"]))


def bot_loop(
    config: dict,
    args: argparse.Namespace,
    stop: threading.Event,
    inp: Input,
    killswitch: Killswitch,
    run_dir: Path,
) -> int:
    capture = ScreenCapture(config["game_region"])
    vision = Vision(config["vision"])

    def clock() -> float:
        return time.monotonic() - inp.paused_s

    flight_log = run_dir / f"flight_{datetime.now():%H%M%S}.csv"
    loop = CrateLoop(vision, inp, capture.grab, stop, config, args.map, clock, flight_log)
    machine = build_machine(config, args, vision, loop, inp)
    try:
        while True:
            frame = capture.grab()
            try:
                machine.tick(frame)
            except LeaveLayer as error:
                log.warning("Layer 1 verlassen: %s", error)
                inp.release_all()
            except Finished:
                log.info("Fertig")
                return EXIT_STOPPED
            except (UnknownStateTimeout, SafeStop, StepFailed) as error:
                killswitch.trigger(str(error))
                save_debug_screenshot(run_dir, capture.grab(), type(error).__name__)
                return (
                    EXIT_UNKNOWN_STATE if isinstance(error, UnknownStateTimeout) else EXIT_SAFE_STOP
                )
            wait(stop, config["loop"]["tick_s"])
    finally:
        if args.layer:
            log.info("Zusammenfassung: %s", dict(loop.stats) or "nichts erledigt")
        capture.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    run_dir = setup_logging(config["logging"]["root"], config["logging"]["level"], "bot")
    stop = threading.Event()
    window = config["window"]
    focused = None if args.dry_run or args.hold_test else lambda: is_foreground(window["title"])
    inp = Input(stop, dry_run=args.dry_run, focused=focused, focus_poll_s=window["poll_s"])
    killswitch = Killswitch(config["keys"]["stop"], stop, inp.release_all)
    killswitch.start()
    log.info("Start (dry_run=%s). Stopp mit %s", args.dry_run, config["keys"]["stop"].upper())
    try:
        countdown(stop, config["loop"]["start_delay_s"])
        log.info("Vordergrund: '%s' (Spiel: '%s')", foreground_title(), window["title"])
        if args.hold_test:
            hold_test(inp, stop, config["hold_test"]["key"], config["hold_test"]["repeat_s"])
        return bot_loop(config, args, stop, inp, killswitch, run_dir)
    except Stopped:
        log.info("Beendet durch Stopp")
        return EXIT_STOPPED
    except Exception:
        log.exception("Unerwarteter Fehler")
        return EXIT_ERROR
    finally:
        inp.release_all()
        killswitch.close()


if __name__ == "__main__":
    sys.exit(main())
