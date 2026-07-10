# ALScan Guided Merge

Safe, transparent, verifiable merge workflow for Ableton Live Sets.

## Concepts

ALScan's Guided Merge helps you combine changes from two divergent versions of an
Ableton Live Set into a single result. Unlike automatic merge tools, ALScan never
modifies your source files. Instead, it:

1. **Analyzes** the three versions (Base, Ours, Theirs) to detect all differences.
2. **Recommends** which Set to use as the foundation for your merged result.
3. **Plans** the sequence of changes you need to make in Ableton Live.
4. **Guides** you through each step with clear Ableton-native instructions.
5. **Tracks** which steps are completed and which need review.
6. **Verifies** the final result against the accepted plan.
7. **Confirms** that none of your source Sets were modified during the workflow.

### Base, Ours, Theirs

- **Base**: The common ancestor — the version you both started from.
- **Ours**: One descendant — your version or one collaborator's version.
- **Theirs**: The other descendant — the other collaborator's version.

This is standard three-way merge terminology. Choose which version is "ours" and
which is "theirs" — the analysis is symmetric, so the labels are for your
convenience.

### Read-only guarantee

ALScan is a read-only analysis tool. Every source `.als` file is treated as
immutable. No source file is ever opened for writing, overwritten, renamed, or
deleted. All changes happen manually in Ableton Live, guided by ALScan's
instructions.

### Recommendations vs. applications

ALScan labels some changes as "automatically reconcilable." This means the
three-way analysis detects a clean resolution — not that ALScan has applied it.
All changes must be performed manually in Ableton Live (or accepted through the
guided workflow when automated operations become available).

## Example workflow

### CLI (interactive)

```bash
# Launch the interactive guided merge wizard
alscan merge guide base.als our-version.als their-version.als

# With unrelated projects (weak lineage)
alscan merge guide --allow-unrelated base.als our-version.als their-version.als

# Non-interactive mode (for scripts)
alscan merge guide --non-interactive base.als our-version.als their-version.als
```

The interactive wizard walks you through:
1. Safety preflight and analysis
2. Foundation selection with comparison table
3. Reviewing and deciding on each operation (Accept/Skip/Defer)
4. Destination preparation guidance
5. Manual execution tracking (Mark complete/Skip/Defer/Save and quit)
6. Manifest saving

### CLI (scripting)

```bash
# Export the manifest for later use
alscan merge plan base.als our-version.als their-version.als --output merge-plan.json

# Resume a saved session
alscan merge resume merge-plan.json

# After completing manual steps, verify the destination
alscan merge verify merge-plan.json destination.als
```

### GUI

The Guided Merge page in the desktop GUI provides a 9-stage wizard with the same
functionality as the CLI. Key features:

- **Save/Open/Resume**: Sessions can be saved to a versioned manifest file and
  reopened later. Changed sources are detected and block unsafe resumption.
- **Unsaved changes**: The GUI tracks unsaved changes and prompts before
  discarding them.
- **Foundation comparison**: Visual comparison cards for Ours, Theirs, Base,
  and Blank Set (advanced).
- **Decision review**: Per-operation detail view with Accept/Skip/Defer controls.
- **Destination validation**: Checks that the destination differs from all sources.
- **Verification**: Run after manual steps to confirm the result.

CLI and GUI use the same manifest format. A session created in the CLI can be
opened in the GUI, and vice versa.

## Foundation choice

ALScan evaluates which source Set requires the least manual work to become the
final merged result:

- **Ours** — Fastest if most changes are in Theirs (and vice versa).
- **Theirs** — Symmetric. Choose whichever has fewer conflicts.
- **Blank Set** — Advanced option. Requires manually recreating every global
  setting and importing every track. Only use when neither branch Set is viable.

The recommended foundation is not a final decision. You can choose any source
as your starting point.

## Manual steps

Each operation in the plan includes:

1. **What** changed and **why** ALScan recommends the action.
2. **Exact source** Set, track name, and values.
3. **Clear Ableton-native instructions** (not developer instructions).
4. **Expected result** so you know when you're done.
5. **How ALScan will verify** the result afterward.

Mark each step complete as you perform it in Ableton Live. ALScan does not
control Ableton or detect your actions automatically.

## Manifest

The merge manifest is a JSON file that contains:

- Session metadata (ID, timestamps, source hashes).
- Foundation recommendation and selection.
- The complete ordered operation plan.
- User decisions for each operation.
- Verification rules and results.
- Source immutability evidence.

The manifest is versioned (format version 1) and designed for forward-compatible
reading. It is never embedded in or written over any source `.als` file.

## Verification

After completing the manual steps, run `alscan merge verify` to compare the
destination Set against the accepted plan. The verification report shows:

- **Passed** operations that match expectations.
- **Failed** operations that differ from expectations.
- **Unverifiable** operations that cannot be automatically checked.
- **Source hash stability** confirming no source file was changed.

A failed verification does not mean the merge is wrong — it means the destination
does not yet match the accepted plan. Review the failed items and adjust the
destination in Ableton Live.

## Privacy

Merge manifests and reports contain structural project metadata including track
names, sample names, plugin names, source paths, and hashes. Review before
sharing. Export the redacted copy (`manifest.redacted_copy()`) for sharing with
collaborators.

## Automation roadmap

The guided merge architecture supports progressive automation:

1. **Current**: All operations are manual. ALScan provides instructions and
   verification.
2. **Planned**: Safe scalar operations (tempo, time signature, track name,
   track color, locator changes) may gain an "Apply Automatically" option.
3. **Future**: Track additions via opaque XML subtree copy, with validation.
4. **Not planned**: Arbitrary merge writing, plugin state reconstruction,
   automation envelope merging, Max for Live internals.

Automated operations will always require:
- Strong lineage confidence.
- Supported Ableton Live version.
- Explicit user approval.
- Preflight validation.
- Write to temporary file first.
- Automatic verification.

## Recovery from mistakes

The merge manifest is your safety net. You can:

1. **Resume** from any saved manifest with `alscan merge resume`.
2. **Re-verify** the destination at any time.
3. **Re-analyze** from scratch if sources have changed.
4. **Start over** by re-running `alscan merge guide` with the same inputs.

Never delete your source Sets. Keep them until the destination has been opened
and validated in Ableton Live.

## Limitations

- ALScan does not interpret or reconstruct plugin states, automation envelopes,
  clip internals, or Max for Live devices.
- Identity matching uses structural evidence and may require manual review for
  tracks with duplicate IDs or ambiguous names.
- The supported Ableton Live generation is Live 12 (MajorVersion 5,
  MinorVersion 10-12). Older or newer versions may be analyzed but automatic
  application is disabled.
- Verification can only check structural metadata. Audio content, plugin sound,
  and mix balance require listening in Ableton Live.

## Supported Ableton Live versions

ALScan targets Live 12 (MajorVersion 5). Files from Live 11 and Live 10
(MinorVersion 10, 11) are also supported for read-only analysis when they share
the same MajorVersion. Files from older generations (Live 9 and earlier,
MajorVersion 4 or below) can be analyzed but automatic application is disabled.
