# Dependency review — 2026-10-12

Minimal lower bounds exclude the identified vulnerable versions. No AI/account
package was introduced. Local resolution: FastAPI0.143.0, Starlette1.7.0,
python-multipart0.0.32, Uvicorn0.54.0, h11.0.16.0; pip check PASS. Current-source
CI separately validates Windows/Linux Python3.12/3.13 and frontend lockfile.

| Dependency | Minimum | Primary basis |
|---|---|---|
|Starlette|1.3.1|[GHSA-82w8-qh3p-5jfq](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq), ignored URL-encoded form limits|
|python-multipart|0.0.31|[header DoS fixed0.0.27](https://github.com/Kludex/python-multipart/security/advisories/GHSA-pp6c-gr5w-3c5g), [query parsing fixed0.0.30](https://github.com/Kludex/python-multipart/security/advisories/GHSA-5rvq-cxj2-64vf);floor31 excludes negative parse_form read-size issue as well|
|h11|0.16|[release notes](https://h11.readthedocs.io/en/v0.16.0/changes.html), malformed chunk endings/request-smuggling fix|

Nexus refuses proxies and URL-encoded imports, limiting those exposure contexts.
This does not justify permitting vulnerable installations. Additive tests cover
malformed h11 chunk terminators. This targeted review is not an exhaustive scan.

Installed license metadata: FastAPI/Pydantic MIT, Starlette/Uvicorn BSD-3,
python-multipart Apache-2.0, h11 MIT. Frontend dependencies/lockfile unchanged.
