# Project Policy

  * Order-status extraction intentionally supports only a single page. Do not
    recommend implementing order-status pagination.
  * For snapshot archive creation and restoration, do not recommend replacing
    `io.BytesIO()` with a disk-backed temporary tar file when the goal is to
    avoid writing unencrypted tar data to the filesystem. Keep the archive in
    memory unless the user explicitly requests a different tradeoff.
