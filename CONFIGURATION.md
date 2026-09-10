# Upload encryption

The service accepts uploaded B50 payloads with `schemaVersion` 1 or 2.
Version 2 can include `serverUrl`, `cardNo`, `password`, and `pcbid`.

Set `B50_ENCRYPTION_KEY` in the service environment before starting the app.
Its value is a base64-encoded 32-byte AES key. When configured, nonempty
cloud source fields are encrypted with AES-256-GCM before storage. The
latest-upload API returns those encrypted fields unchanged, as in the
existing deployment. Without the key, the existing plaintext behavior is
preserved. The app does not automatically load a `.env` file.

Keep the original key when migrating or restoring data. Keep it outside Git;
do not include actual credentials or database files in commits.

The old server-side Maomani fetch API has been retired. This service receives
uploads from clients; it no longer fetches scores from that provider.
