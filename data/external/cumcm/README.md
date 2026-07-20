# CUMCM official problem corpus

Downloaded from the official China Undergraduate Mathematical Contest in Modeling website on 2026-07-20.

The large archives and extracted files are intentionally ignored by Git. This file records their provenance and integrity information.

## Local layout

- `raw/`: original official archives, 4 files, 210,288,492 bytes total.
- `extracted/`: extracted yearly packages, 135 files, 656,134,805 bytes total.
- 2022 and 2023 contain nested archives; their C-problem archives have also been extracted into `extracted/<year>/C/`.

## Source manifest

| Year | Official page | Local archive | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| 2025 | [problem page](https://www.mcm.edu.cn/html_cn/node/03c91a444e62eee81a3740fa97a461a6.html) | `raw/cumcm-2025-problems.zip` | 52,097,165 | `CEF6262C24EE3017BDAB4CA255299C7B47B2700AD89FD773ADDDE7E241E7E4DE` |
| 2024 | [problem page](https://www.mcm.edu.cn/html_cn/node/a0c1fb5c31d43551f08cd8ad16870444.html) | `raw/cumcm-2024-problems.zip` | 105,537,539 | `38D9EFFCEDE947354F9E9A9C2B4FC68947D83A77C2FF75737E9A662888158726` |
| 2023 | [problem page](https://www.mcm.edu.cn/html_cn/node/c74d72127066f510a5723a94b5323a26.html) | `raw/cumcm-2023-problems.rar` | 41,797,492 | `37B1010672ADCF35831E798264CC69DB616027F2287CFEAE3C4EE6DAF03AE4E6` |
| 2022 | [problem page](https://www.mcm.edu.cn/html_cn/node/388239ded4b057d37b7b8e51e33fe903.html) | `raw/cumcm-2022-problems.rar` | 10,856,296 | `C27EB1B665F070341E134F5DC13BB2AF469230424FF2EEDABF594EEE708BFEE4` |

## C-problem files confirmed

- 2025: `C题.pdf`, `附件.xlsx`.
- 2024: `C题.pdf`, `附件1.xlsx`, `附件2.xlsx`, and three files under `附件3/`.
- 2023: `C题.pdf`, `附件1.xlsx` through `附件4.xlsx`.
- 2022: `C题.pdf`, `附件.xlsx`.

## Usage boundary

This download contains official problem statements and supplied data only. Paper-showcase images were not downloaded because the official showcase pages prohibit unauthorized republication. The project should store paper metadata and official page URLs unless separate permission or a user-provided authorized copy is available.
