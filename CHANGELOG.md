# Changelog

## [0.0.5](https://github.com/bakerkj/ha-gc-manager/compare/v0.0.4...v0.0.5) (2026-11-22)


### Bug Fixes

* drain in-flight GC work on unload, reload and failed setup ([#102](https://github.com/bakerkj/ha-gc-manager/issues/102)) ([084e3a8](https://github.com/bakerkj/ha-gc-manager/commit/084e3a854be1c87e9ef4925702413fb5c604dab8))
* hold scheduled operations until the startup freeze has run ([#104](https://github.com/bakerkj/ha-gc-manager/issues/104)) ([939145f](https://github.com/bakerkj/ha-gc-manager/commit/939145ffe0d072a4d68bac0d3eb4450c222d3abf))
* unfreeze the heap when the integration is disabled ([#103](https://github.com/bakerkj/ha-gc-manager/issues/103)) ([8631023](https://github.com/bakerkj/ha-gc-manager/commit/8631023ef6a3b0defc9de0818689334bf324ab92))
* walk each object count only while its sensor is enabled ([#105](https://github.com/bakerkj/ha-gc-manager/issues/105)) ([d99c403](https://github.com/bakerkj/ha-gc-manager/commit/d99c4033ff94760923ebb39a2f03f6fb4f3d7913))


### Miscellaneous Chores

* **deps:** lock file maintenance ([#92](https://github.com/bakerkj/ha-gc-manager/issues/92)) ([5ccf570](https://github.com/bakerkj/ha-gc-manager/commit/5ccf570b54442401d51339795fc51ba8eb0122f9))
* **deps:** lock file maintenance ([#95](https://github.com/bakerkj/ha-gc-manager/issues/95)) ([cbf5cbc](https://github.com/bakerkj/ha-gc-manager/commit/cbf5cbc0ea57c18709d58253e7571f8ec605a96a))
* **deps:** lock file maintenance ([#97](https://github.com/bakerkj/ha-gc-manager/issues/97)) ([229c4e5](https://github.com/bakerkj/ha-gc-manager/commit/229c4e506a07aeefa7dae1f954b2502f7db67953))
* **deps:** update anthropics/claude-code-action action to v1.0.271 ([#89](https://github.com/bakerkj/ha-gc-manager/issues/89)) ([2b1a22c](https://github.com/bakerkj/ha-gc-manager/commit/2b1a22c2ce2543fdbfbd6ef46173f3d8d222aff3))
* **deps:** update anthropics/claude-code-action action to v1.0.280 ([#100](https://github.com/bakerkj/ha-gc-manager/issues/100)) ([d9794a0](https://github.com/bakerkj/ha-gc-manager/commit/d9794a079dca131522ae01c91d6c0ae11fa4ce3d))
* **deps:** update dependency uv to v0.13.8 ([#94](https://github.com/bakerkj/ha-gc-manager/issues/94)) ([b119a63](https://github.com/bakerkj/ha-gc-manager/commit/b119a63a612e47027b22b0fb2f44dadecb0dd212))
* **deps:** update dependency uv to v0.13.9 ([#98](https://github.com/bakerkj/ha-gc-manager/issues/98)) ([1c18c82](https://github.com/bakerkj/ha-gc-manager/commit/1c18c82c3d1fb5ca39de09fbe6e4606a0581ad2b))
* **deps:** update github-actions ([#101](https://github.com/bakerkj/ha-gc-manager/issues/101)) ([7c18c70](https://github.com/bakerkj/ha-gc-manager/commit/7c18c70cdc22a6e49a5a017c0ee6efb2e48d2e2c))
* **deps:** update github-actions ([#96](https://github.com/bakerkj/ha-gc-manager/issues/96)) ([22ece41](https://github.com/bakerkj/ha-gc-manager/commit/22ece41cff5616fc9104f151bdcc930036aaf5ad))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.17.6 ([#99](https://github.com/bakerkj/ha-gc-manager/issues/99)) ([6efe48e](https://github.com/bakerkj/ha-gc-manager/commit/6efe48e69f6e554bdb04e5b99f9293049655ed4c))
* **deps:** update pre-commit hook kjanat/actionlint to v1.17.1 ([#90](https://github.com/bakerkj/ha-gc-manager/issues/90)) ([9d79622](https://github.com/bakerkj/ha-gc-manager/commit/9d796221f9a0fdf2d2c75f2d6f06b74adaf97055))
* **deps:** update pre-commit hooks ([#93](https://github.com/bakerkj/ha-gc-manager/issues/93)) ([c52f419](https://github.com/bakerkj/ha-gc-manager/commit/c52f419d1a99d118247892ebf4db4e36d0787685))

## [0.0.4](https://github.com/bakerkj/ha-gc-manager/compare/v0.0.3...v0.0.4) (2026-11-07)


### Features

* diagnostics download and a per-operation event ([#84](https://github.com/bakerkj/ha-gc-manager/issues/84)) ([caa7b95](https://github.com/bakerkj/ha-gc-manager/commit/caa7b9548751591560c2396bf8b9a0289baa4eb7))
* gate the periodic re-freeze on a measured gen-2 pause target ([#69](https://github.com/bakerkj/ha-gc-manager/issues/69)) ([9b6231e](https://github.com/bakerkj/ha-gc-manager/commit/9b6231e97ab0c9db4d185bc5536d53d677ad811a))
* push sensor state the moment a GC operation lands ([#83](https://github.com/bakerkj/ha-gc-manager/issues/83)) ([29b690a](https://github.com/bakerkj/ha-gc-manager/commit/29b690a04bbc59d4bb76be903cdcdd5eec1b625f))


### Bug Fixes

* **deps:** pin the HA test plugin so the locked HA tracks releases ([#61](https://github.com/bakerkj/ha-gc-manager/issues/61)) ([d8de27d](https://github.com/bakerkj/ha-gc-manager/commit/d8de27d31d1755b6efc590c1501930c1e66fce04))


### Miscellaneous Chores

* **ci:** standardize uv usage across workflows ([#60](https://github.com/bakerkj/ha-gc-manager/issues/60)) ([d85534c](https://github.com/bakerkj/ha-gc-manager/commit/d85534c8f44326c5ea615c06884162759a78015e))
* **deps:** lock file maintenance ([#62](https://github.com/bakerkj/ha-gc-manager/issues/62)) ([79dc2a3](https://github.com/bakerkj/ha-gc-manager/commit/79dc2a3f0cb91f31457fe6de48eac33bf75f0682))
* **deps:** lock file maintenance ([#66](https://github.com/bakerkj/ha-gc-manager/issues/66)) ([686621d](https://github.com/bakerkj/ha-gc-manager/commit/686621d510fd08d8f3bdc7b50882ca05cb875f90))
* **deps:** lock file maintenance ([#67](https://github.com/bakerkj/ha-gc-manager/issues/67)) ([8e5edc3](https://github.com/bakerkj/ha-gc-manager/commit/8e5edc300ce41d5b9bbe8e5f55f947854ef31ecc))
* **deps:** lock file maintenance ([#73](https://github.com/bakerkj/ha-gc-manager/issues/73)) ([97ddd0c](https://github.com/bakerkj/ha-gc-manager/commit/97ddd0cd44e508b0799ea3519a304c3c96ef2bef))
* **deps:** lock file maintenance ([#75](https://github.com/bakerkj/ha-gc-manager/issues/75)) ([3836f53](https://github.com/bakerkj/ha-gc-manager/commit/3836f53e8eea7829111f6c60b915abfccfeb8d45))
* **deps:** lock file maintenance ([#78](https://github.com/bakerkj/ha-gc-manager/issues/78)) ([02ae397](https://github.com/bakerkj/ha-gc-manager/commit/02ae3977f683f0fd7ec7750baca010d9cc219698))
* **deps:** lock file maintenance ([#80](https://github.com/bakerkj/ha-gc-manager/issues/80)) ([ad14b32](https://github.com/bakerkj/ha-gc-manager/commit/ad14b32fec08ec1a2a368828ef3e6ea7223e7347))
* **deps:** update anthropics/claude-code-action action to v1.0.255 ([#55](https://github.com/bakerkj/ha-gc-manager/issues/55)) ([ecaaaed](https://github.com/bakerkj/ha-gc-manager/commit/ecaaaed96c356ad587e99c02874ba44e2b20dd7f))
* **deps:** update anthropics/claude-code-action action to v1.0.263 ([#63](https://github.com/bakerkj/ha-gc-manager/issues/63)) ([a56c87a](https://github.com/bakerkj/ha-gc-manager/commit/a56c87aa6946e3cbbd619575893e50cd48a7c7e6))
* **deps:** update anthropics/claude-code-action action to v1.0.267 ([#76](https://github.com/bakerkj/ha-gc-manager/issues/76)) ([25aabee](https://github.com/bakerkj/ha-gc-manager/commit/25aabee10f6f05bea73e607b37fe0c4a21f0d780))
* **deps:** update dependency uv to v0.13.1 ([#48](https://github.com/bakerkj/ha-gc-manager/issues/48)) ([5c23546](https://github.com/bakerkj/ha-gc-manager/commit/5c23546b06cf9cd57691af972d1eee779c96bde5))
* **deps:** update dependency uv to v0.13.3 ([#51](https://github.com/bakerkj/ha-gc-manager/issues/51)) ([872168d](https://github.com/bakerkj/ha-gc-manager/commit/872168d129772444f77e4063d837ebd94287f954))
* **deps:** update dependency uv to v0.13.4 ([#54](https://github.com/bakerkj/ha-gc-manager/issues/54)) ([356cb9d](https://github.com/bakerkj/ha-gc-manager/commit/356cb9da8ce00c9b871920ab89be0689fbdea83a))
* **deps:** update dependency uv to v0.13.5 ([#56](https://github.com/bakerkj/ha-gc-manager/issues/56)) ([4803233](https://github.com/bakerkj/ha-gc-manager/commit/4803233e4b787ef66080a7b281f41ddf5210de6a))
* **deps:** update dependency uv to v0.13.6 ([#64](https://github.com/bakerkj/ha-gc-manager/issues/64)) ([c868668](https://github.com/bakerkj/ha-gc-manager/commit/c86866821082255c14801f660f8b291a0b6b1b10))
* **deps:** update dependency uv to v0.13.7 ([#77](https://github.com/bakerkj/ha-gc-manager/issues/77)) ([da52101](https://github.com/bakerkj/ha-gc-manager/commit/da5210193375528b1daf51f8d12d5421a65779eb))
* **deps:** update github-actions ([#50](https://github.com/bakerkj/ha-gc-manager/issues/50)) ([42795e6](https://github.com/bakerkj/ha-gc-manager/commit/42795e6dd389917f1181b069c2a61ada1fbec031))
* **deps:** update github-actions ([#52](https://github.com/bakerkj/ha-gc-manager/issues/52)) ([d9b19b8](https://github.com/bakerkj/ha-gc-manager/commit/d9b19b8034d2c90ed47896c1dec170dbf88708fc))
* **deps:** update github-actions ([#57](https://github.com/bakerkj/ha-gc-manager/issues/57)) ([9af6c03](https://github.com/bakerkj/ha-gc-manager/commit/9af6c03c5c963ea8ca3f7e0540645c7b799ecc19))
* **deps:** update github-actions ([#74](https://github.com/bakerkj/ha-gc-manager/issues/74)) ([d2f0c4a](https://github.com/bakerkj/ha-gc-manager/commit/d2f0c4af373c82bda880fc90ac041b7edfb3cb45))
* **deps:** update github-actions ([#79](https://github.com/bakerkj/ha-gc-manager/issues/79)) ([57c9c97](https://github.com/bakerkj/ha-gc-manager/commit/57c9c97b0e089d44937b735ccfc23f2dae13162e))
* **deps:** update j178/prek-action action to v3.1.0 ([#53](https://github.com/bakerkj/ha-gc-manager/issues/53)) ([0602c85](https://github.com/bakerkj/ha-gc-manager/commit/0602c854f937400c2be83ee5dfde69e6ea935fdb))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.17.1 ([#49](https://github.com/bakerkj/ha-gc-manager/issues/49)) ([80ac700](https://github.com/bakerkj/ha-gc-manager/commit/80ac700525dda2549d98e7ee432758bfd4e49ed0))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.17.2 ([#58](https://github.com/bakerkj/ha-gc-manager/issues/58)) ([e93a195](https://github.com/bakerkj/ha-gc-manager/commit/e93a195b1edbdc3265340512060639927c04772b))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.17.4 ([#81](https://github.com/bakerkj/ha-gc-manager/issues/81)) ([908faf3](https://github.com/bakerkj/ha-gc-manager/commit/908faf32c098c06502df9ecf2a212ae12c5d274e))
* **deps:** update pre-commit hooks ([#65](https://github.com/bakerkj/ha-gc-manager/issues/65)) ([ee7d6f0](https://github.com/bakerkj/ha-gc-manager/commit/ee7d6f01fe911435ff03be9a254248c4ff56e842))
* **python:** require Python 3.14.5 or newer ([#82](https://github.com/bakerkj/ha-gc-manager/issues/82)) ([27a8132](https://github.com/bakerkj/ha-gc-manager/commit/27a8132b5cfab28fdceb4256238c2bb7df0c031b))
* **renovate:** enable lockFileMaintenance ([#59](https://github.com/bakerkj/ha-gc-manager/issues/59)) ([5ddeea8](https://github.com/bakerkj/ha-gc-manager/commit/5ddeea818e39f4df703131ce5dfe6569a1606ffe))


### Continuous Integration

* **claude:** gate on-demand [@claude](https://github.com/claude) workflow to repo owner ([#45](https://github.com/bakerkj/ha-gc-manager/issues/45)) ([2bda50a](https://github.com/bakerkj/ha-gc-manager/commit/2bda50aba3b6066fc79b519618a364e39f48c04f))

## [0.0.3](https://github.com/bakerkj/ha-gc-manager/compare/v0.0.2...v0.0.3) (2026-10-11)


### Features

* keep automatic gc off during a start, until the startup freeze ([#36](https://github.com/bakerkj/ha-gc-manager/issues/36)) ([8bd2533](https://github.com/bakerkj/ha-gc-manager/commit/8bd2533fd50ca9a2699a29486b442502ff7ff56a))
* make the frozen/tracked count sampler interval configurable ([#43](https://github.com/bakerkj/ha-gc-manager/issues/43)) ([d5cf7be](https://github.com/bakerkj/ha-gc-manager/commit/d5cf7be7845504e8d6a79ba4f3d2fbbda458bc96))


### Bug Fixes

* **renovate:** don't duplicate runs-on detection with the built-in manager ([#19](https://github.com/bakerkj/ha-gc-manager/issues/19)) ([fdf95c6](https://github.com/bakerkj/ha-gc-manager/commit/fdf95c6afc884445761a9784698134e165aa26a8))
* skip the object-count walks while both count sensors are disabled ([#35](https://github.com/bakerkj/ha-gc-manager/issues/35)) ([11a69c9](https://github.com/bakerkj/ha-gc-manager/commit/11a69c96de5e83cbcac1893b95c1f19ee589dfa4))


### Miscellaneous Chores

* **deps:** update anthropics/claude-code-action action to v1.0.225 ([#14](https://github.com/bakerkj/ha-gc-manager/issues/14)) ([d08656f](https://github.com/bakerkj/ha-gc-manager/commit/d08656fbf6f20107c9dbb0b258c1d66984a8031f))
* **deps:** update anthropics/claude-code-action action to v1.0.226 ([#25](https://github.com/bakerkj/ha-gc-manager/issues/25)) ([a74d53d](https://github.com/bakerkj/ha-gc-manager/commit/a74d53df25da9b960b33fdb296a7aa166ff22b1c))
* **deps:** update anthropics/claude-code-action action to v1.0.231 ([#26](https://github.com/bakerkj/ha-gc-manager/issues/26)) ([e11bb36](https://github.com/bakerkj/ha-gc-manager/commit/e11bb364751a747d1ff647dbe0bad65f8e788c69))
* **deps:** update anthropics/claude-code-action action to v1.0.236 ([#29](https://github.com/bakerkj/ha-gc-manager/issues/29)) ([e45dfb9](https://github.com/bakerkj/ha-gc-manager/commit/e45dfb9f9f57963a5cdb070a2d68a18d4f84a25e))
* **deps:** update anthropics/claude-code-action action to v1.0.237 ([#32](https://github.com/bakerkj/ha-gc-manager/issues/32)) ([d38e691](https://github.com/bakerkj/ha-gc-manager/commit/d38e691e014db66fccd351663f586be5ed203905))
* **deps:** update anthropics/claude-code-action action to v1.0.244 ([#41](https://github.com/bakerkj/ha-gc-manager/issues/41)) ([341a239](https://github.com/bakerkj/ha-gc-manager/commit/341a239b31e68c9d5faf60de4e1d2075314cab70))
* **deps:** update astral-sh/setup-uv action to v10.2.0 ([#27](https://github.com/bakerkj/ha-gc-manager/issues/27)) ([5350e83](https://github.com/bakerkj/ha-gc-manager/commit/5350e83f08e90f7f0ca458b3e33d388521fd373f))
* **deps:** update dependency ubuntu to v26 ([#17](https://github.com/bakerkj/ha-gc-manager/issues/17)) ([7537a98](https://github.com/bakerkj/ha-gc-manager/commit/7537a98aa25bd17024e1d6bcc74c95711d795a16))
* **deps:** update dependency uv to v0.12.14 ([#15](https://github.com/bakerkj/ha-gc-manager/issues/15)) ([9a93147](https://github.com/bakerkj/ha-gc-manager/commit/9a93147258edb88028851a513299fad0a810f64e))
* **deps:** update dependency uv to v0.12.15 ([#21](https://github.com/bakerkj/ha-gc-manager/issues/21)) ([7ec2258](https://github.com/bakerkj/ha-gc-manager/commit/7ec2258bc0e374736244b4947c5e7df3fa49989c))
* **deps:** update dependency uv to v0.12.17 ([#23](https://github.com/bakerkj/ha-gc-manager/issues/23)) ([f45428f](https://github.com/bakerkj/ha-gc-manager/commit/f45428f42f38e1bb49cbe7432b58ad9d2af4cd4b))
* **deps:** update dependency uv to v0.12.20 ([#30](https://github.com/bakerkj/ha-gc-manager/issues/30)) ([9216c2b](https://github.com/bakerkj/ha-gc-manager/commit/9216c2b65b089352938f01338f3dbf102c830f1f))
* **deps:** update dependency uv to v0.12.22 ([#34](https://github.com/bakerkj/ha-gc-manager/issues/34)) ([09b4aa3](https://github.com/bakerkj/ha-gc-manager/commit/09b4aa390ddea4c8f7ecfa0f77f41736c22b8429))
* **deps:** update dependency uv to v0.12.23 ([#37](https://github.com/bakerkj/ha-gc-manager/issues/37)) ([d883126](https://github.com/bakerkj/ha-gc-manager/commit/d88312634bb1ec1199b7c1a3371d4b89d2b0c05f))
* **deps:** update dependency uv to v0.13.0 ([#40](https://github.com/bakerkj/ha-gc-manager/issues/40)) ([e69d225](https://github.com/bakerkj/ha-gc-manager/commit/e69d2256b336b36050343dce838e271c7ebb7ea9))
* **deps:** update github-actions ([#38](https://github.com/bakerkj/ha-gc-manager/issues/38)) ([966ae04](https://github.com/bakerkj/ha-gc-manager/commit/966ae04f715a7d78b43ced597205319802891a66))
* **deps:** update github-actions ([#42](https://github.com/bakerkj/ha-gc-manager/issues/42)) ([41f6843](https://github.com/bakerkj/ha-gc-manager/commit/41f68431d16f639dfde4586618f835bdd640c3d7))
* **deps:** update pre-commit hook alessandrojcm/commitlint-pre-commit-hook to v9.27.0 ([#28](https://github.com/bakerkj/ha-gc-manager/issues/28)) ([ae999e1](https://github.com/bakerkj/ha-gc-manager/commit/ae999e17ab4b1c00ad4a683e0d7d3256b55e6bd2))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.16.10 ([#33](https://github.com/bakerkj/ha-gc-manager/issues/33)) ([bc8493e](https://github.com/bakerkj/ha-gc-manager/commit/bc8493e5beb59622de17313a877c0f2b025f0a10))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.17.0 ([#39](https://github.com/bakerkj/ha-gc-manager/issues/39)) ([683debe](https://github.com/bakerkj/ha-gc-manager/commit/683debe783bf8fadb5c84acb852a2dbe03dd448d))
* **deps:** update pre-commit hook rbubley/mirrors-prettier to v3.9.10 ([#44](https://github.com/bakerkj/ha-gc-manager/issues/44)) ([777abd6](https://github.com/bakerkj/ha-gc-manager/commit/777abd6530b18da5e85c5f50a91b45cb0feb2a7b))
* **deps:** update pre-commit hook rbubley/mirrors-prettier to v3.9.7 ([#22](https://github.com/bakerkj/ha-gc-manager/issues/22)) ([83fbe34](https://github.com/bakerkj/ha-gc-manager/commit/83fbe3417fe55f8de068a4fb439265389c474ff2))
* **deps:** update pre-commit hooks ([#24](https://github.com/bakerkj/ha-gc-manager/issues/24)) ([d7ce737](https://github.com/bakerkj/ha-gc-manager/commit/d7ce737d71fed6889f3e8e5acd09bbbf16331d5d))
* **deps:** update pre-commit hooks ([#31](https://github.com/bakerkj/ha-gc-manager/issues/31)) ([e1e935f](https://github.com/bakerkj/ha-gc-manager/commit/e1e935fe6298cf64e07f03a72b1ca2626ed171db))
* switch actionlint pre-commit hook from rhysd (stale) to kjanat fork ([#20](https://github.com/bakerkj/ha-gc-manager/issues/20)) ([fe0d55f](https://github.com/bakerkj/ha-gc-manager/commit/fe0d55fa1820751a244579d8a198f4fc3677db54))

## [0.0.2](https://github.com/bakerkj/ha-gc-manager/compare/v0.0.1...v0.0.2) (2026-09-14)


### Miscellaneous Chores

* **deps:** update dependency uv to v0.12.13 ([#13](https://github.com/bakerkj/ha-gc-manager/issues/13)) ([240f90b](https://github.com/bakerkj/ha-gc-manager/commit/240f90b299d5f29312280c9ddb17d6812d88b3aa))
* **deps:** update github-actions ([#10](https://github.com/bakerkj/ha-gc-manager/issues/10)) ([fff8483](https://github.com/bakerkj/ha-gc-manager/commit/fff848390f8c4f0922b9f6638d18c06ab68a344d))
* **deps:** update github-actions ([#12](https://github.com/bakerkj/ha-gc-manager/issues/12)) ([2a228c8](https://github.com/bakerkj/ha-gc-manager/commit/2a228c87c40ae73d5ec5ffe6161363134bd452ea))
* **deps:** update mcr.microsoft.com/devcontainers/python docker tag to v3 ([#8](https://github.com/bakerkj/ha-gc-manager/issues/8)) ([94eaf2c](https://github.com/bakerkj/ha-gc-manager/commit/94eaf2cccde6e2c70d224276954e9c30e52edbd6))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.16.7 ([#11](https://github.com/bakerkj/ha-gc-manager/issues/11)) ([26264f5](https://github.com/bakerkj/ha-gc-manager/commit/26264f547201e19c89c845b3d1e57fec2fdb4783))

## 0.0.1 (2026-09-14)


### Features

* add GC Manager integration ([6b6270d](https://github.com/bakerkj/ha-gc-manager/commit/6b6270dd8d6f40cef76a1361d9c97cdad540ddf1))
