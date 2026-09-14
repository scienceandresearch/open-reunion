# Repository content and rights

This is an unofficial fan recreation. The new implementation is MIT licensed;
original game rights are not transferred or relicensed by this project. The
repository is not a clean-room implementation and has not received blanket
legal clearance for its code, presentation or branding.

## Included

- New Python/C implementation and synthetic unit tests.
- File-format offsets, hashes, identifiers and filename inventories needed to
  interpret a user's local copy; these are not executable or asset payloads.
- Reconstructed rules and presentation timing/sequence code. Some cinematic
  choreography closely follows the original. It remains part of the faithful
  recreation and requires consideration in any broader rights review.
- The optional modern JSON checkpoint collection: numeric campaign state,
  gameplay identifiers and our checkpoint descriptions. Historical event logs
  containing decoded original prose are cleared. Artwork, sound, executable
  blocks and active dialogue are not embedded in that collection.
- Separately licensed audio source/notices. The one allowed nested ZIP is the
  pinned upstream libopenmpt source archive, not an original game archive.

## Excluded

Original executables and bytecode dumps; art, bitmap fonts, music, sound effects,
animation frames and decoded text files; catalog/startup/converted content
bundles; original DOS saves; private research reports/screenshots; personal save
directories; build caches and older asset-inclusive release archives.

The importer reads the required files from the user's legally obtained copy.
It never downloads original game content. Local extraction avoids including
those files in this repository; it does not establish permission for every use
of the underlying work. "Abandonware" describes availability, not a license.
See the [U.S. Copyright Office overview](https://www.copyright.gov/what-is-copyright/)
for the distinction between copyright and trademarks and the rights involved.

## Technical checks

tools/audit_repository.py checks the curated working tree or exact staged Git
blobs, rejects generated paths and media/binary extensions, checks the pinned
third-party archive hash, and flags potential secrets and large embedded binary
literals. tools/check_checkpoints.py verifies all checkpoint membership/hashes.
The source packager reuses the public-file audit.

These checks cannot determine copyright ownership, detect every disguised
payload, or prove absence of all protected expression. Review changes and
release attachments, including nested archives, before sharing. The repository
was prepared with fresh Git history so private development artifacts were never
committed. Do not import the old development directory or its historical ZIPs
into this repository.
