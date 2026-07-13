# Slice 06: Safe repository target

Release: 0.2
Depends on: slice 05

## Contract unlocked

A manifest repository path can be resolved, inspected, and initialized beneath
the manifest directory without symlink traversal or path-replacement escape.

## API seam

- `study_agent.adapters.filesystem.repository_target`: sole target resolver and
  safe initializer for procedural `init` and lifecycle setup.
- `ResolvedRepositoryTarget`: verified manifest root/parent identity plus relative
  tail; it contains no study-domain state.

Every existing component is opened no-follow relative to a verified directory
fd. The creation tail is made beneath the verified parent and parent/target
identity is checked before publication. The implementation must not validate a
path and later re-resolve the same untrusted string with `mkdir(parents=True)`.

## Runnable checkpoint

Initialize a nested target from the normative fixture, then reject absolute,
dot/parent traversal, symlinked intermediate/final components, non-directory
parents, parent replacement during creation, and a non-empty incompatible target.

## Verification

- Procedural `init` and lifecycle setup use the same resolver/initializer.
- Symlink-intermediate and parent-replacement race fixtures cannot write outside
  the manifest/explicit trusted root.
- Compatible existing repository is a noop; config mismatch is a conflict.
- Initialization retains existing fsync/publication/recovery guarantees.
- Resolution/inspection is offline and writes nothing; initialization writes
  only within the verified target.

## Human review checkpoint

Security-review the target-directory threat model. Extra roots remain explicit
trusted-host inputs and are never read from manifest content.
