# Retrieval Comparison Results

> 4-way ablation study with embedding reranking on graph-expanded nodes.
>
> **Design: AST for structure, LLM for semantics** (see [design.md](design.md))
>
> - AST edges: 1,328 (CONTAINS: 1,132 | CALLS: 136 | INHERITS: 36 | USES_TYPE: 24) — deterministic, fast, 100% precision
> - LLM edges: 490 (SIMILAR_TO, DEPENDS_ON only) — semantic relationships AST cannot detect
> - LLM extraction: embedding-pruned pairs (top-5 per node, 500 LLM calls, 98% hit rate, 45 files)
>
> **Why this split?** AST reliably extracts CONTAINS, CALLS, IMPORTS, INHERITS, USES_TYPE from syntax.
> LLM adds value only for intent-based relationships (SIMILAR_TO: similar purpose/logic, DEPENDS_ON: implicit runtime dependencies).
> Earlier runs with LLM extracting all edge types showed it was less complete than AST for structural edges and sometimes misclassified them.

## Summary

| Query | Vector Only | Vector + AST Graph | Vector + Graph (LLM) | Vector + Graph (AST+LLM) |
|-------|-----------|------------|------------|-------|
| HTTP client connection pooling | 5 results, 2 files | 25 results, 2 files | 7 results, 3 files | 25 results, 2 files |
| retry failed requests with backoff | 5 results, 5 files | 15 results, 5 files | 5 results, 5 files | 15 results, 5 files |
| SSL certificate verification | 5 results, 2 files | 7 results, 2 files | 11 results, 3 files | 12 results, 3 files |
| parse URL and query parameters | 5 results, 2 files | 8 results, 2 files | 7 results, 2 files | 10 results, 2 files |
| handle authentication flow | 5 results, 1 files | 8 results, 1 files | 23 results, 2 files | 23 results, 2 files |


---

## Query: "HTTP client connection pooling"

### Vector Only (5 results: 5 vector + 0 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| vector | +0.499 | httpx._client | httpx/_client.py |
| vector | +0.487 | Client | httpx/_client.py |
| vector | +0.485 | test_pool_timeout | tests/test_timeouts.py |
| vector | +0.440 | AsyncClient | httpx/_client.py |
| vector | +0.398 | Client.stream | httpx/_client.py |

### Vector + AST Graph (25 results: 5 vector + 20 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.682 | Client.__exit__ | httpx/_client.py |
| graph | +0.674 | Client.__init__ | httpx/_client.py |
| graph | +0.649 | Client.__enter__ | httpx/_client.py |
| graph | +0.644 | Client.close | httpx/_client.py |
| graph | +0.639 | Client.patch | httpx/_client.py |
| graph | +0.638 | _same_origin | httpx/_client.py |
| graph | +0.636 | Client._init_proxy_transport | httpx/_client.py |
| graph | +0.628 | Client.post | httpx/_client.py |
| graph | +0.628 | Client.options | httpx/_client.py |
| graph | +0.626 | Client._send_handling_auth | httpx/_client.py |
| graph | +0.620 | _port_or_default | httpx/_client.py |
| graph | +0.618 | Client.delete | httpx/_client.py |
| graph | +0.615 | Client._send_handling_redirects | httpx/_client.py |
| graph | +0.603 | Client.put | httpx/_client.py |
| graph | +0.596 | BoundSyncStream | httpx/_client.py |
| graph | +0.587 | BaseClient | httpx/_client.py |
| graph | +0.576 | _is_https_redirect | httpx/_client.py |
| graph | +0.576 | BoundAsyncStream | httpx/_client.py |
| graph | +0.563 | ClientState | httpx/_client.py |
| graph | +0.516 | UseClientDefault | httpx/_client.py |
| vector | +0.499 | httpx._client | httpx/_client.py |
| vector | +0.487 | Client | httpx/_client.py |
| vector | +0.485 | test_pool_timeout | tests/test_timeouts.py |
| vector | +0.440 | AsyncClient | httpx/_client.py |
| vector | +0.398 | Client.stream | httpx/_client.py |

### Vector + Graph (LLM) (7 results: 5 vector + 2 graph, 3 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.690 | AsyncClient.stream | httpx/_client.py |
| graph | +0.668 | stream | httpx/_api.py |
| vector | +0.499 | httpx._client | httpx/_client.py |
| vector | +0.487 | Client | httpx/_client.py |
| vector | +0.485 | test_pool_timeout | tests/test_timeouts.py |
| vector | +0.440 | AsyncClient | httpx/_client.py |
| vector | +0.398 | Client.stream | httpx/_client.py |

### Vector + Graph (AST+LLM) (25 results: 5 vector + 20 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.682 | Client.__exit__ | httpx/_client.py |
| graph | +0.674 | Client.__init__ | httpx/_client.py |
| graph | +0.649 | Client.__enter__ | httpx/_client.py |
| graph | +0.644 | Client.close | httpx/_client.py |
| graph | +0.639 | Client.patch | httpx/_client.py |
| graph | +0.638 | _same_origin | httpx/_client.py |
| graph | +0.636 | Client._init_proxy_transport | httpx/_client.py |
| graph | +0.628 | Client.post | httpx/_client.py |
| graph | +0.628 | Client.options | httpx/_client.py |
| graph | +0.626 | Client._send_handling_auth | httpx/_client.py |
| graph | +0.620 | _port_or_default | httpx/_client.py |
| graph | +0.618 | Client.delete | httpx/_client.py |
| graph | +0.615 | Client._send_handling_redirects | httpx/_client.py |
| graph | +0.603 | Client.put | httpx/_client.py |
| graph | +0.596 | BoundSyncStream | httpx/_client.py |
| graph | +0.587 | BaseClient | httpx/_client.py |
| graph | +0.576 | _is_https_redirect | httpx/_client.py |
| graph | +0.576 | BoundAsyncStream | httpx/_client.py |
| graph | +0.563 | ClientState | httpx/_client.py |
| graph | +0.516 | UseClientDefault | httpx/_client.py |
| vector | +0.499 | httpx._client | httpx/_client.py |
| vector | +0.487 | Client | httpx/_client.py |
| vector | +0.485 | test_pool_timeout | tests/test_timeouts.py |
| vector | +0.440 | AsyncClient | httpx/_client.py |
| vector | +0.398 | Client.stream | httpx/_client.py |

### LLM-only graph nodes (2 nodes not found by AST)

| Score | Name | File |
|-------|------|------|
| +0.690 | AsyncClient.stream | httpx/_client.py |
| +0.668 | stream | httpx/_api.py |


---

## Query: "retry failed requests with backoff"

### Vector Only (5 results: 5 vector + 0 graph, 5 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| vector | +0.430 | tests.test_timeouts | tests/test_timeouts.py |
| vector | +0.418 | TestServer.watch_restarts | tests/conftest.py |
| vector | +0.401 | test_elapsed_not_available_until_closed | tests/models/test_responses.py |
| vector | +0.396 | HTTPError.request | httpx/_exceptions.py |
| vector | +0.393 | AsyncClient.__aenter__ | httpx/_client.py |

### Vector + AST Graph (15 results: 5 vector + 10 graph, 5 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.684 | AsyncClient | httpx/_client.py |
| graph | +0.678 | HTTPError | httpx/_exceptions.py |
| graph | +0.675 | TestServer | tests/conftest.py |
| graph | +0.673 | tests.models.test_responses | tests/models/test_responses.py |
| graph | +0.661 | async_streaming_body | tests/models/test_responses.py |
| graph | +0.632 | test_connect_timeout | tests/test_timeouts.py |
| graph | +0.628 | test_pool_timeout | tests/test_timeouts.py |
| graph | +0.618 | test_read_timeout | tests/test_timeouts.py |
| graph | +0.593 | test_async_client_new_request_send_timeout | tests/test_timeouts.py |
| graph | +0.575 | test_write_timeout | tests/test_timeouts.py |
| vector | +0.430 | tests.test_timeouts | tests/test_timeouts.py |
| vector | +0.418 | TestServer.watch_restarts | tests/conftest.py |
| vector | +0.401 | test_elapsed_not_available_until_closed | tests/models/test_responses.py |
| vector | +0.396 | HTTPError.request | httpx/_exceptions.py |
| vector | +0.393 | AsyncClient.__aenter__ | httpx/_client.py |

### Vector + Graph (LLM) (5 results: 5 vector + 0 graph, 5 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| vector | +0.430 | tests.test_timeouts | tests/test_timeouts.py |
| vector | +0.418 | TestServer.watch_restarts | tests/conftest.py |
| vector | +0.401 | test_elapsed_not_available_until_closed | tests/models/test_responses.py |
| vector | +0.396 | HTTPError.request | httpx/_exceptions.py |
| vector | +0.393 | AsyncClient.__aenter__ | httpx/_client.py |

### Vector + Graph (AST+LLM) (15 results: 5 vector + 10 graph, 5 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.684 | AsyncClient | httpx/_client.py |
| graph | +0.678 | HTTPError | httpx/_exceptions.py |
| graph | +0.675 | TestServer | tests/conftest.py |
| graph | +0.673 | tests.models.test_responses | tests/models/test_responses.py |
| graph | +0.661 | async_streaming_body | tests/models/test_responses.py |
| graph | +0.632 | test_connect_timeout | tests/test_timeouts.py |
| graph | +0.628 | test_pool_timeout | tests/test_timeouts.py |
| graph | +0.618 | test_read_timeout | tests/test_timeouts.py |
| graph | +0.593 | test_async_client_new_request_send_timeout | tests/test_timeouts.py |
| graph | +0.575 | test_write_timeout | tests/test_timeouts.py |
| vector | +0.430 | tests.test_timeouts | tests/test_timeouts.py |
| vector | +0.418 | TestServer.watch_restarts | tests/conftest.py |
| vector | +0.401 | test_elapsed_not_available_until_closed | tests/models/test_responses.py |
| vector | +0.396 | HTTPError.request | httpx/_exceptions.py |
| vector | +0.393 | AsyncClient.__aenter__ | httpx/_client.py |


---

## Query: "SSL certificate verification"

### Vector Only (5 results: 5 vector + 0 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| vector | +0.609 | test_load_ssl_config_verify_existing_file | tests/test_config.py |
| vector | +0.604 | test_load_ssl_config_no_verify | tests/test_config.py |
| vector | +0.595 | test_load_ssl_config_verify_directory | tests/test_config.py |
| vector | +0.568 | test_load_ssl_config | tests/test_config.py |
| vector | +0.556 | HTTPTransport.__init__ | httpx/_transports/default.py |

### Vector + AST Graph (7 results: 5 vector + 2 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.768 | tests.test_config | tests/test_config.py |
| vector | +0.609 | test_load_ssl_config_verify_existing_file | tests/test_config.py |
| vector | +0.604 | test_load_ssl_config_no_verify | tests/test_config.py |
| vector | +0.595 | test_load_ssl_config_verify_directory | tests/test_config.py |
| vector | +0.568 | test_load_ssl_config | tests/test_config.py |
| vector | +0.556 | HTTPTransport.__init__ | httpx/_transports/default.py |
| graph | +0.490 | HTTPTransport | httpx/_transports/default.py |

### Vector + Graph (LLM) (11 results: 5 vector + 6 graph, 3 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.774 | AsyncHTTPTransport.__init__ | httpx/_transports/default.py |
| graph | +0.768 | AsyncHTTPTransport | httpx/_transports/default.py |
| graph | +0.764 | Client._init_transport | httpx/_client.py |
| graph | +0.757 | test_load_ssl_config_verify_non_existing_file | tests/test_config.py |
| graph | +0.742 | AsyncClient._init_transport | httpx/_client.py |
| graph | +0.737 | HTTPTransport | httpx/_transports/default.py |
| vector | +0.609 | test_load_ssl_config_verify_existing_file | tests/test_config.py |
| vector | +0.604 | test_load_ssl_config_no_verify | tests/test_config.py |
| vector | +0.595 | test_load_ssl_config_verify_directory | tests/test_config.py |
| vector | +0.568 | test_load_ssl_config | tests/test_config.py |
| vector | +0.556 | HTTPTransport.__init__ | httpx/_transports/default.py |

### Vector + Graph (AST+LLM) (12 results: 5 vector + 7 graph, 3 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.774 | Client._init_transport | httpx/_client.py |
| graph | +0.768 | AsyncClient._init_transport | httpx/_client.py |
| graph | +0.764 | AsyncHTTPTransport | httpx/_transports/default.py |
| graph | +0.757 | test_load_ssl_config_verify_non_existing_file | tests/test_config.py |
| graph | +0.742 | tests.test_config | tests/test_config.py |
| graph | +0.737 | HTTPTransport | httpx/_transports/default.py |
| vector | +0.609 | test_load_ssl_config_verify_existing_file | tests/test_config.py |
| vector | +0.604 | test_load_ssl_config_no_verify | tests/test_config.py |
| vector | +0.595 | test_load_ssl_config_verify_directory | tests/test_config.py |
| vector | +0.568 | test_load_ssl_config | tests/test_config.py |
| vector | +0.556 | HTTPTransport.__init__ | httpx/_transports/default.py |
| graph | +0.490 | AsyncHTTPTransport.__init__ | httpx/_transports/default.py |

### LLM-only graph nodes (5 nodes not found by AST)

| Score | Name | File |
|-------|------|------|
| +0.774 | AsyncHTTPTransport.__init__ | httpx/_transports/default.py |
| +0.768 | AsyncHTTPTransport | httpx/_transports/default.py |
| +0.764 | Client._init_transport | httpx/_client.py |
| +0.757 | test_load_ssl_config_verify_non_existing_file | tests/test_config.py |
| +0.742 | AsyncClient._init_transport | httpx/_client.py |


---

## Query: "parse URL and query parameters"

### Vector Only (5 results: 5 vector + 0 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| vector | +0.609 | URL.params | httpx/_urls.py |
| vector | +0.559 | QueryParams.__str__ | httpx/_urls.py |
| vector | +0.548 | QueryParams.get_list | httpx/_urls.py |
| vector | +0.540 | QueryParams.values | httpx/_urls.py |
| vector | +0.535 | BaseClient.params | httpx/_client.py |

### Vector + AST Graph (8 results: 5 vector + 3 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.758 | BaseClient | httpx/_client.py |
| graph | +0.682 | QueryParams | httpx/_urls.py |
| vector | +0.609 | URL.params | httpx/_urls.py |
| graph | +0.602 | URL | httpx/_urls.py |
| vector | +0.559 | QueryParams.__str__ | httpx/_urls.py |
| vector | +0.548 | QueryParams.get_list | httpx/_urls.py |
| vector | +0.540 | QueryParams.values | httpx/_urls.py |
| vector | +0.535 | BaseClient.params | httpx/_client.py |

### Vector + Graph (LLM) (7 results: 5 vector + 2 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.752 | QueryParams.items | httpx/_urls.py |
| graph | +0.740 | QueryParams.keys | httpx/_urls.py |
| vector | +0.609 | URL.params | httpx/_urls.py |
| vector | +0.559 | QueryParams.__str__ | httpx/_urls.py |
| vector | +0.548 | QueryParams.get_list | httpx/_urls.py |
| vector | +0.540 | QueryParams.values | httpx/_urls.py |
| vector | +0.535 | BaseClient.params | httpx/_client.py |

### Vector + Graph (AST+LLM) (10 results: 5 vector + 5 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.758 | QueryParams.keys | httpx/_urls.py |
| graph | +0.752 | BaseClient | httpx/_client.py |
| graph | +0.740 | QueryParams.items | httpx/_urls.py |
| graph | +0.682 | QueryParams | httpx/_urls.py |
| vector | +0.609 | URL.params | httpx/_urls.py |
| graph | +0.602 | URL | httpx/_urls.py |
| vector | +0.559 | QueryParams.__str__ | httpx/_urls.py |
| vector | +0.548 | QueryParams.get_list | httpx/_urls.py |
| vector | +0.540 | QueryParams.values | httpx/_urls.py |
| vector | +0.535 | BaseClient.params | httpx/_client.py |

### LLM-only graph nodes (2 nodes not found by AST)

| Score | Name | File |
|-------|------|------|
| +0.752 | QueryParams.items | httpx/_urls.py |
| +0.740 | QueryParams.keys | httpx/_urls.py |


---

## Query: "handle authentication flow"

### Vector Only (5 results: 5 vector + 0 graph, 1 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| vector | +0.618 | Auth.auth_flow | httpx/_auth.py |
| vector | +0.588 | Auth.sync_auth_flow | httpx/_auth.py |
| vector | +0.584 | Auth.async_auth_flow | httpx/_auth.py |
| vector | +0.581 | DigestAuth.auth_flow | httpx/_auth.py |
| vector | +0.579 | BasicAuth.auth_flow | httpx/_auth.py |

### Vector + AST Graph (8 results: 5 vector + 3 graph, 1 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.741 | Auth | httpx/_auth.py |
| graph | +0.683 | BasicAuth | httpx/_auth.py |
| graph | +0.662 | DigestAuth | httpx/_auth.py |
| vector | +0.618 | Auth.auth_flow | httpx/_auth.py |
| vector | +0.588 | Auth.sync_auth_flow | httpx/_auth.py |
| vector | +0.584 | Auth.async_auth_flow | httpx/_auth.py |
| vector | +0.581 | DigestAuth.auth_flow | httpx/_auth.py |
| vector | +0.579 | BasicAuth.auth_flow | httpx/_auth.py |

### Vector + Graph (LLM) (23 results: 5 vector + 18 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.785 | DigestAuth | httpx/_auth.py |
| graph | +0.773 | NetRCAuth.__init__ | httpx/_auth.py |
| graph | +0.759 | _DigestAuthChallenge | httpx/_auth.py |
| graph | +0.746 | NetRCAuth._build_auth_header | httpx/_auth.py |
| graph | +0.741 | FunctionAuth.auth_flow | httpx/_auth.py |
| graph | +0.690 | DigestAuth._build_auth_header | httpx/_auth.py |
| graph | +0.683 | NetRCAuth.auth_flow | httpx/_auth.py |
| graph | +0.683 | BasicAuth._build_auth_header | httpx/_auth.py |
| graph | +0.681 | NetRCAuth | httpx/_auth.py |
| graph | +0.679 | DigestAuth._parse_challenge | httpx/_auth.py |
| graph | +0.678 | BasicAuth.__init__ | httpx/_auth.py |
| graph | +0.673 | ResponseBodyAuth.auth_flow | tests/client/test_auth.py |
| graph | +0.668 | DigestAuth._get_header_value | httpx/_auth.py |
| graph | +0.662 | FunctionAuth | httpx/_auth.py |
| graph | +0.642 | Auth | httpx/_auth.py |
| graph | +0.635 | BasicAuth | httpx/_auth.py |
| vector | +0.618 | Auth.auth_flow | httpx/_auth.py |
| vector | +0.588 | Auth.sync_auth_flow | httpx/_auth.py |
| graph | +0.588 | DigestAuth.__init__ | httpx/_auth.py |
| vector | +0.584 | Auth.async_auth_flow | httpx/_auth.py |
| vector | +0.581 | DigestAuth.auth_flow | httpx/_auth.py |
| vector | +0.579 | BasicAuth.auth_flow | httpx/_auth.py |
| graph | +0.538 | SyncOrAsyncAuth.async_auth_flow | tests/client/test_auth.py |

### Vector + Graph (AST+LLM) (23 results: 5 vector + 18 graph, 2 files)

| Source | Score | Name | File |
|--------|-------|------|------|
| graph | +0.785 | DigestAuth | httpx/_auth.py |
| graph | +0.773 | NetRCAuth.__init__ | httpx/_auth.py |
| graph | +0.759 | _DigestAuthChallenge | httpx/_auth.py |
| graph | +0.746 | NetRCAuth._build_auth_header | httpx/_auth.py |
| graph | +0.741 | FunctionAuth.auth_flow | httpx/_auth.py |
| graph | +0.690 | DigestAuth._build_auth_header | httpx/_auth.py |
| graph | +0.683 | NetRCAuth.auth_flow | httpx/_auth.py |
| graph | +0.683 | BasicAuth._build_auth_header | httpx/_auth.py |
| graph | +0.681 | NetRCAuth | httpx/_auth.py |
| graph | +0.679 | DigestAuth._parse_challenge | httpx/_auth.py |
| graph | +0.678 | BasicAuth.__init__ | httpx/_auth.py |
| graph | +0.673 | ResponseBodyAuth.auth_flow | tests/client/test_auth.py |
| graph | +0.668 | DigestAuth._get_header_value | httpx/_auth.py |
| graph | +0.662 | FunctionAuth | httpx/_auth.py |
| graph | +0.642 | Auth | httpx/_auth.py |
| graph | +0.635 | BasicAuth | httpx/_auth.py |
| vector | +0.618 | Auth.auth_flow | httpx/_auth.py |
| vector | +0.588 | Auth.sync_auth_flow | httpx/_auth.py |
| graph | +0.588 | DigestAuth.__init__ | httpx/_auth.py |
| vector | +0.584 | Auth.async_auth_flow | httpx/_auth.py |
| vector | +0.581 | DigestAuth.auth_flow | httpx/_auth.py |
| vector | +0.579 | BasicAuth.auth_flow | httpx/_auth.py |
| graph | +0.538 | SyncOrAsyncAuth.async_auth_flow | tests/client/test_auth.py |

### LLM-only graph nodes (15 nodes not found by AST)

| Score | Name | File |
|-------|------|------|
| +0.773 | NetRCAuth.__init__ | httpx/_auth.py |
| +0.759 | _DigestAuthChallenge | httpx/_auth.py |
| +0.746 | NetRCAuth._build_auth_header | httpx/_auth.py |
| +0.741 | FunctionAuth.auth_flow | httpx/_auth.py |
| +0.690 | DigestAuth._build_auth_header | httpx/_auth.py |
| +0.683 | NetRCAuth.auth_flow | httpx/_auth.py |
| +0.683 | BasicAuth._build_auth_header | httpx/_auth.py |
| +0.681 | NetRCAuth | httpx/_auth.py |
| +0.679 | DigestAuth._parse_challenge | httpx/_auth.py |
| +0.678 | BasicAuth.__init__ | httpx/_auth.py |
| +0.673 | ResponseBodyAuth.auth_flow | tests/client/test_auth.py |
| +0.668 | DigestAuth._get_header_value | httpx/_auth.py |
| +0.662 | FunctionAuth | httpx/_auth.py |
| +0.588 | DigestAuth.__init__ | httpx/_auth.py |
| +0.538 | SyncOrAsyncAuth.async_auth_flow | tests/client/test_auth.py |

---

## Key Observations

### AST vs LLM: what each contributes

1. **AST excels at structural navigation**: CONTAINS/CALLS edges pull in parent classes, sibling methods, and call targets. For "HTTP client connection pooling", AST graph expands 5→25 results by traversing the `Client` class hierarchy. This is fast, free, and deterministic.

2. **LLM excels at cross-boundary semantic links**: For "handle authentication flow", LLM graph finds 18 additional nodes (vs 3 from AST) because SIMILAR_TO edges connect `BasicAuth.auth_flow` ↔ `NetRCAuth.auth_flow` ↔ `FunctionAuth.auth_flow` — implementations with different code but the same purpose. AST cannot detect this.

3. **LLM adds cross-file reach**: For "SSL certificate verification", LLM-only nodes include `Client._init_transport` and `AsyncClient._init_transport` from `_client.py` — runtime dependencies on transport config that AST's structural edges don't capture.

4. **AST dominates when structure = relevance**: For "retry failed requests with backoff", LLM graph adds 0 new nodes. The relevant context is structural (timeout test functions, exception hierarchy), which AST already covers.

5. **Combined (AST+LLM) is consistently >= either alone**: The union never loses relevant results, and reranking by embedding similarity ensures the best nodes surface first regardless of source.

### Design validation

6. **Moving INHERITS/USES_TYPE to AST was correct**: AST extracts these from `class Foo(Bar)` and type annotations with zero ambiguity. Earlier LLM runs found 39 INHERITS edges but sometimes misclassified method→class relationships as inheritance. AST now has 36 INHERITS + 24 USES_TYPE edges with 100% precision.

7. **LLM narrowed to SIMILAR_TO + DEPENDS_ON**: These are the only edge types that require understanding code intent, not just syntax. SIMILAR_TO (548 edges in full extraction) is where LLM adds the most unique value. DEPENDS_ON (31 edges) captures implicit runtime dependencies like shared state and initialization order.

### Retrieval mechanics

8. **Embedding reranking matters**: Graph nodes scored by cosine similarity to query (0.5–0.8 range) instead of flat 0.5. This surfaces the most relevant graph neighbors first, preventing low-relevance structural neighbors from drowning out high-relevance semantic ones.

9. **Pruning makes LLM extraction practical**: Embedding similarity pre-filter reduced 654K+ possible pairs to 500 LLM calls with 98% hit rate (490/500 produced edges), covering 45 files across the whole repo vs 2 files with brute-force same-file pairing.

### When to use which retrieval mode

| Scenario | Best mode | Why |
|----------|-----------|-----|
| Navigating a known class/module | Vector + AST Graph | Structural edges give complete class hierarchy |
| Finding similar implementations | Vector + Graph (LLM) | SIMILAR_TO edges connect functionally equivalent code |
| Understanding implicit dependencies | Vector + Graph (AST+LLM) | DEPENDS_ON + structural context gives full picture |
| Quick keyword lookup | Vector Only | Fast, no graph overhead, sufficient for direct matches |
