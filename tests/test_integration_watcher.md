# Test Watcher Integration

The `test_watcher_integration` test is designed to verify the interaction between `fileclip` and `fileclip_watcher` in a simulated container environment (local Ubuntu container). Here’s the expected sequence:

## Setup
Both `fileclip` and `fileclip_watcher` operate on the same shared directory (e.g., `/tmp/pytest-of-developer/pytest-62/test_watcher_integration0/workspace/.fileclip`) to simulate a shared mount.

## Watcher Start
The `run_watcher` fixture starts `fileclip_watcher` in a background thread, monitoring the `.fileclip` directory for request files (`fileclip_request_*.json`).

## Fileclip Execution
The test runs `fileclip_main()` with arguments mimicking:
```bash
pdm run fileclip test.txt --use-watcher --watcher-timeout 20
```

- Detects the container environment (`mock_is_container`).
- Writes a request JSON (`fileclip_request_<uuid>.json`) with the `copy_files` action and the test file path.
- Waits for the watcher to process it and produce a result JSON (`fileclip_results_<uuid>.json`).

## Watcher Processing

The watcher performs the following actions:

- Detects the request JSON.
- Reads the `copy_files` action and calls `copy_files` with the translated path (the same as the container path in this test since `container_dir = host_dir`).
- Writes a result JSON indicating success or failure.

## Success Criteria

The test passes if:

- The request JSON is deleted by the watcher.
- The result JSON is created, read, and deleted by `fileclip`.
- The watcher logs confirm the file was processed ("Copied 1 file(s)").
- The mocked `_copy_files_direct` is called with the correct path.

## Verification

The test checks logs and asserts that `_copy_files_direct` was called with the expected path.