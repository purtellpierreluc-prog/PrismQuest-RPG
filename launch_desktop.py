"""Keep freeze_support before GUI imports: native windows spawn a child process."""
import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()
    from steam_client.runtime import launch, report_startup_error
    try:
        launch()
    except Exception as exc:
        report_startup_error(exc)
        raise SystemExit(1) from exc
