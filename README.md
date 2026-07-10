# prj-apex-resolution-cache

Serves proven exact resolutions and attributed hints for the Apex Investigator
(design 14). Implements the Orchestrator's `ResolutionCacheClient` contract:

- **Level 1 (exact):** reads the projected candidate the Feedback Pipeline writes
  to Redis, then **revalidates it against the authoritative Spanner resolution** —
  the projection is never trusted as action content. Only an INDEPENDENT, ACTIVE,
  intrinsically-safe resolution at ≥0.85 success over ≥3 attempts auto-applies.
- **Levels 2/3 (hints):** structural (Neo4j) and semantic (Vector) hint sources,
  behind ports as stubs until that infrastructure lands. Run concurrently under a
  bounded budget; a slow or failing source contributes nothing.

`revalidate` / `lookup_level_one` / `lookup_structural_hints` /
`lookup_semantic_hints` / cascading `lookup` are exposed over authenticated HTTP.
Redis/Neo4j/Vector/Spanner failures degrade to none/empty, never blocking an
Investigation.

## Development

```sh
just sync
just emulator   # Spanner emulator (Docker) for the integration tests
just test
just lint
```
