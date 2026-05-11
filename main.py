"""Repository entry point for a lightweight end-to-end demo."""


def main() -> int:
    """Run the demo pipeline and print a concise summary."""
    try:
        from src.agents.orchestrator import run_demo_pipeline
        from src.agents.responder import render_console_report
    except ModuleNotFoundError as error:
        print(
            "Missing dependency while starting the demo pipeline. "
            "Install project requirements first with `pip install -r requirements.txt`.\n"
            f"Details: {error}"
        )
        return 1

    snapshot = run_demo_pipeline()
    print(render_console_report(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
