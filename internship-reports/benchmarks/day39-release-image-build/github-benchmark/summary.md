# Day39 GitHub Image Build Benchmark

Date: 2026-07-03

Repository: `ranxi2001/agentcube`

## Runs

| Case | Branch | Commit | Run | Job result |
| --- | --- | --- | --- | --- |
| Baseline | `ci/image-build-baseline-benchmark` | `4e737fc8deb994490917c7f47e4c05dee8fd85a8` | <https://github.com/ranxi2001/agentcube/actions/runs/28636642514> | success |
| Scheme A | `ci/image-build-scheme-a-benchmark` | `60e584919d235898078be2f51452a3463adc4246` | <https://github.com/ranxi2001/agentcube/actions/runs/28636642076> | success |

Both branches also passed the regular push validation workflows. The benchmark workflow did not log in to GHCR, did not push images, and did not package or push Helm charts.

## Image Build Times

| Image | Baseline elapsed | Scheme A elapsed | Speedup | Reduction |
| --- | ---: | ---: | ---: | ---: |
| workloadmanager | 1423s | 182s | 7.82x | 87.2% |
| router | 33s | 4s | 8.25x | 87.9% |
| picod | 132s | 122s | 1.08x | 7.6% |
| Sum of three buildx commands | 1588s | 308s | 5.16x | 80.6% |
| Benchmark job wall time | 1610s | 331s | 4.86x | 79.4% |

## Key BuildKit Steps

| Step | Baseline | Scheme A | Speedup | Reduction |
| --- | ---: | ---: | ---: | ---: |
| workloadmanager arm64 Go build | 1404.5s | 169.4s | 8.29x | 87.9% |
| router arm64 Go build | 32.5s | 3.4s | 9.56x | 89.5% |
| picod arm64 Go build | 9.6s | 0.9s | 10.67x | 90.6% |
| picod arm64 `apt-get install python3` | 128.8s | 119.1s | 1.08x | 7.5% |

## Raw Logs

- Baseline: `baseline-28636642514/`
- Scheme A: `scheme-a-28636642076/`

## Interpretation

Scheme A changes only the three Dockerfile builder base images to `FROM --platform=$BUILDPLATFORM ... AS builder`. On GitHub's x64 runner, that keeps Go compilation on the native builder platform while still producing `linux/amd64` and `linux/arm64` artifacts via `GOOS` / `GOARCH`.

The result validates the main hypothesis: the release workflow bottleneck is the target-platform arm64 Go compiler running through QEMU. The workloadmanager arm64 Go build dropped from 1404.5s to 169.4s on the same GitHub runner class. Router and PicoD Go build steps show the same direction.

PicoD remains mostly unchanged at the image level because its dominant cost is not Go compilation. Its arm64 Ubuntu runtime layer still runs `apt-get update && apt-get install -y python3` under target-platform emulation, taking 119.1s in Scheme A. That should be handled as a follow-up runtime image optimization, not mixed into the minimal Scheme A PR.
