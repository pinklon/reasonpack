# ReasonPack direct-remux source capture v19

Source-only optional performance lane. No change to installed VPS acquisition service, root ledger, Gmail writer, publication authority or model provider access.

## Evidence from the first real canary

The owner supplied https://www.youtube.com/watch?v=jEOUUAPC1sc, Greg Isenberg's 30:50 Gemini 4 Argon video. Anonymous YouTube acquisition worked from the Mac Studio while the VPS received bot-verification refusal. The reference-kit v1 full source package and native private Reader verified successfully.

The original canonical source build took 858.10 seconds for 30:50 video, primarily because legacy bin/reasonpack build invokes ffmpeg video re-encoding with libx264 medium preset. This wastes compute on research/text extraction when YouTube already serves compressed MP4 video and AAC/M4A audio.

The source metadata of this actual canary lists direct format 399 (1080p AV1 in MP4) and format 140 (AAC in M4A). Its legacy output was 1080p H.264 with AAC and ~222 MiB after re-encoding. A separate opt-in direct-remux path should preserve selected compressed video bytes and mux without decode/encode.

## Implementation

New command: bin/reasonpack build-fast URL NEW_OUTPUT_DIR. It calls ops/direct-remux-pack.py, distinct from legacy build URL OUT_DIR. It requires one canonical https://www.youtube.com/watch?v=<exact 11-char ID> and a NEW output directory.

The command uses yt-dlp with --ignore-config and --no-playlist, no cookie file, no browser-cookie extraction, no account keys. It selects an already compressed MP4 video stream plus AAC/M4A audio and uses yt-dlp/FFmpeg's stream-copy mux; it extracts separate AAC audio with ffmpeg -c:a copy. No libx264, no video quality recompression, no automatic fallback to a costly transcode, and no total video duration cutoff. If media tracks cannot be remuxed as valid MP4/AAC, it fails clearly and leaves the old compatibility build unchanged for explicit operator use.

It probes video/audio codecs and positive matched durations, captures original English YouTube VTT captions or English fallback, transforms them into timestamp-sourced plain text, checks near-end caption coverage, and creates the unchanged canonical reasonpack-v1 seven-member package:

video.mp4, audio.m4a, source.json, ffprobe.json, captions.vtt, transcript.txt, transcript-status.json, plus manifest.json and SHA256SUMS.txt.

The manifest notes mediaPreparation=direct-mp4-aac-remux-no-video-encode as provenance. The command calls the same canonical bin/reasonpack verify on the candidate before atomically publishing a newly named private directory. The Reader Edition and other downstream tools need no forked schema.

## Qualification

tests/test-direct-remux-pack.py stubs download/probe operations and runs the actual canonical ReasonPack verifier on a deterministic tiny synthetic package. It verifies the no-cookie/no-reencode format selection, source URL host/path/ID restrictions, rejecting incorrect audio/video codecs, duration mismatches, missing existing output, captions normalization and the old build command retained unchanged. This fixture does not demonstrate valid playable video. Require a real Mac Studio network canary with ffprobe/manifest+native Reader and an explicit successful timing measurement before claiming operational speedup.

If direct media is unavailable, stop rather than bypass YouTube account restrictions or automatically start expensive transcoding. Never claim the source video is independently factually verified merely because package digests match. This does not replace owner-signed Gmail admission and immutable service custody in PR #18.

Videos several hours long remain supported by streaming SHA and per-stage checkpoints, not a video-duration limit. No arbitrary full-mission timeout is added.

## Regional-caption fallback

Accept source English tracks in order en-orig, en, then en-US/en-GB/en-* regional variants, keeping only the single selected VTT in the canonical source inventory. Unavailable original English and regional English still fail closed rather than substituting another language or running unexpected paid transcription.

## Rolling-caption normalization

The original VTT remains captured verbatim. The normalized transcript groups payload by WebVTT cue and removes the longest previously spoken word overlap, both within one rolling cue and across successive cues, retaining only novel words. It does not treat caption cue IDs as spoken text. Timestamp coverage uses the maximum cue endpoint, which accepts valid overlapping cues, and both MM:SS.mmm and HH:MM:SS.mmm timestamp forms. This heuristic is for readable search/reasoning text, not an independently verified verbatim transcription; disputed quotes must be checked against the source audio or VTT.
