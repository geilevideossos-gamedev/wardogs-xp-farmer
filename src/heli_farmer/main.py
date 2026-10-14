import argparse
import logging
import sys
import threading
from pathlib import Path

from heli_farmer.capture import ScreenCapture
from heli_farmer.config import load_config
from heli_farmer.inputs import Input
from heli_farmer.killswitch import Killswitch, Stopped, wait
from heli_farmer.logs import save_debug_screenshot, setup_logging
from heli_farmer.states import Detectors, StateMachine, UnknownStateTimeout, Watchdog

log = logging.getLogger(__name__)

EXIT_STOPPED = 0
EXIT_ERROR = 1
EXIT_UNKNOWN_STATE = 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="heli-farmer")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="keine Eingaben senden, nur loggen")
    parser.add_argument("--hold-test", action="store_true", help="hält eine Taste bis zum Stopp")
    return parser.parse_args(argv)


def hold_test(
    inp: Input, stop: threading.Event, key: str, repeat_s: float, start_delay_s: float
) -> None:
    log.info(
        "Hold-Test: in %s s wird '%s' gedrückt gehalten. Jetzt ins Zielfenster wechseln",
        start_delay_s,
        key,
    )
    wait(stop, start_delay_s)
    log.info("Hold-Test: halte '%s' gedrückt", key)
    while True:
        inp.key_down(key)
        wait(stop, repeat_s)


def bot_loop(config: dict, stop: threading.Event, killswitch: Killswitch, run_dir: Path) -> int:
    capture = ScreenCapture(config["game_region"])
    machine = StateMachine(Detectors(), {}, Watchdog(config["timeouts"]["unknown_state_s"]))
    try:
        while True:
            frame = capture.grab()
            try:
                machine.tick(frame)
            except UnknownStateTimeout as error:
                killswitch.trigger(str(error))
                save_debug_screenshot(run_dir, frame, "unknown_state")
                return EXIT_UNKNOWN_STATE
            wait(stop, config["loop"]["tick_s"])
    finally:
        capture.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    run_dir = setup_logging(config["logging"]["root"], config["logging"]["level"], "bot")
    stop = threading.Event()
    inp = Input(stop, dry_run=args.dry_run)
    killswitch = Killswitch(config["keys"]["stop"], stop, inp.release_all)
    killswitch.start()
    log.info("Start (dry_run=%s). Stopp mit %s", args.dry_run, config["keys"]["stop"].upper())
    try:
        if args.hold_test:
            settings = config["hold_test"]
            hold_test(inp, stop, settings["key"], settings["repeat_s"], settings["start_delay_s"])
        return bot_loop(config, stop, killswitch, run_dir)
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
