"""
Locust load test for vLLM serving endpoint.

Sends realistic prompts that mirror actual GraphRAG workloads:
- Agent reasoning with tool calls
- RAG queries with retrieved code context
- JSON relationship extraction
- Simple Q&A (baseline)

Usage:
    # Headless, 1-10 concurrent users, 60s run
    locust -f loadtest/locustfile.py --headless \
        -u 10 --spawn-rate 2 -t 60s \
        --csv loadtest/results

    # With web UI
    locust -f loadtest/locustfile.py
"""
import json
import os
import random
import threading
import time

from locust import HttpUser, task, between, events

API_KEY = os.environ.get("LLM_API_KEY", "graphrag-local-key-change-me")
MODEL = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

# Thread-safe token counter
_lock = threading.Lock()
_token_counts = {"prompt": 0, "completion": 0}


@events.quitting.add_listener
def _save_token_counts(environment, **kwargs):
    path = os.path.join(os.path.dirname(__file__), "token_counts.json")
    with open(path, "w") as f:
        json.dump(_token_counts, f)
    print(f"\nToken counts saved to {path}: {_token_counts}")


# --- Shared context blocks (simulating RAG retrieval results) ---

SYSTEM_PROMPT_AGENT = (
    "You are a code retrieval agent. You help developers understand codebases by "
    "searching for relevant symbols and reading source code. You have access to three tools:\n"
    "1. search_code(query) - vector search over code symbols\n"
    "2. search_code_with_graph(query) - hybrid vector + graph search\n"
    "3. read_symbol_source(symbol_name) - read full source code of a symbol\n\n"
    "Use the tools to find relevant code, then synthesize an answer. "
    "Be specific — reference actual class names, methods, and file paths."
)

RETRIEVED_CONTEXT_AUTH = (
    "## Retrieved code context:\n\n"
    "### httpx/_auth.py :: BasicAuth (class)\n"
    "```python\n"
    "class BasicAuth(Auth):\n"
    "    def __init__(self, username: typing.Union[str, bytes], password: typing.Union[str, bytes]):\n"
    "        self._auth_header = self._build_auth_header(username, password)\n\n"
    "    def auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:\n"
    "        request.headers['Authorization'] = self._auth_header\n"
    "        yield request\n"
    "```\n\n"
    "### httpx/_auth.py :: DigestAuth (class)\n"
    "```python\n"
    "class DigestAuth(Auth):\n"
    "    def __init__(self, username: typing.Union[str, bytes], password: typing.Union[str, bytes]):\n"
    "        self._username = username\n"
    "        self._password = password\n\n"
    "    def auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:\n"
    "        response = yield request\n"
    "        if response.status_code != 401:\n"
    "            return\n"
    "        # Parse www-authenticate header and build digest response\n"
    "        header = response.headers['www-authenticate']\n"
    "        challenge = self._parse_challenge(header)\n"
    "        request.headers['Authorization'] = self._build_digest_header(challenge, request)\n"
    "        yield request\n"
    "```\n\n"
    "### httpx/_auth.py :: NetRCAuth (class)\n"
    "```python\n"
    "class NetRCAuth(Auth):\n"
    "    def __init__(self, file: typing.Optional[str] = None):\n"
    "        self._netrc_info = netrc.netrc(file)\n\n"
    "    def auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:\n"
    "        auth_info = self._netrc_info.authenticators(request.url.host)\n"
    "        if auth_info:\n"
    "            request.headers['Authorization'] = self._build_auth_header(auth_info[0], auth_info[2])\n"
    "        yield request\n"
    "```\n\n"
    "### httpx/_client.py :: Client._build_auth (method)\n"
    "```python\n"
    "def _build_auth(self, auth: AuthTypes) -> Auth:\n"
    "    if isinstance(auth, tuple):\n"
    "        return BasicAuth(username=auth[0], password=auth[1])\n"
    "    elif callable(auth):\n"
    "        return FunctionAuth(func=auth)\n"
    "    return auth\n"
    "```\n\n"
    "### httpx/_config.py :: Limits (class)\n"
    "```python\n"
    "class Limits:\n"
    "    def __init__(self, *, max_connections: int = None, max_keepalive_connections: int = None,\n"
    "                 keepalive_expiry: float = 5.0):\n"
    "        self.max_connections = max_connections\n"
    "        self.max_keepalive_connections = max_keepalive_connections\n"
    "        self.keepalive_expiry = keepalive_expiry\n"
    "```\n"
)

RETRIEVED_CONTEXT_TRANSPORT = (
    "## Retrieved code context:\n\n"
    "### httpx/_transports/default.py :: HTTPTransport (class)\n"
    "```python\n"
    "class HTTPTransport(BaseTransport):\n"
    "    def __init__(self, verify: VerifyTypes = True, cert: CertTypes = None,\n"
    "                 http1: bool = True, http2: bool = False, limits: Limits = DEFAULT_LIMITS,\n"
    "                 trust_env: bool = True, proxy: Proxy = None, uds: str = None,\n"
    "                 local_address: str = None, retries: int = 0, socket_options: typing.Iterable = None):\n"
    "        self._pool = httpcore.ConnectionPool(\n"
    "            ssl_context=ssl_context, max_connections=limits.max_connections,\n"
    "            max_keepalive_connections=limits.max_keepalive_connections,\n"
    "            keepalive_expiry=limits.keepalive_expiry, http1=http1, http2=http2,\n"
    "            uds=uds, local_address=local_address, retries=retries,\n"
    "            socket_options=socket_options)\n\n"
    "    def handle_request(self, request: Request) -> Response:\n"
    "        resp = self._pool.handle_request(httpcore.Request(\n"
    "            method=request.method, url=httpcore.URL(...),\n"
    "            headers=request.headers.raw, content=request.stream))\n"
    "        return Response(status_code=resp.status, headers=resp.headers,\n"
    "                       stream=resp.stream, request=request)\n"
    "```\n\n"
    "### httpx/_transports/default.py :: AsyncHTTPTransport (class)\n"
    "```python\n"
    "class AsyncHTTPTransport(AsyncBaseTransport):\n"
    "    def __init__(self, verify=True, cert=None, http1=True, http2=False,\n"
    "                 limits=DEFAULT_LIMITS, trust_env=True, proxy=None):\n"
    "        self._pool = httpcore.AsyncConnectionPool(...)\n\n"
    "    async def handle_async_request(self, request: Request) -> Response:\n"
    "        resp = await self._pool.handle_async_request(...)\n"
    "        return Response(status_code=resp.status, ...)\n"
    "```\n\n"
    "### httpx/_models.py :: Request (class)\n"
    "```python\n"
    "class Request:\n"
    "    def __init__(self, method: str, url: URL, *, params=None, headers=None,\n"
    "                 cookies=None, content=None, data=None, files=None, json=None, stream=None):\n"
    "        self.method = method.upper()\n"
    "        self.url = self._prepare_url(url)\n"
    "        self.headers = self._prepare_headers(headers)\n"
    "        self.stream = self._prepare_content(content, data, files, json)\n"
    "```\n\n"
    "### httpx/_models.py :: Response (class)\n"
    "```python\n"
    "class Response:\n"
    "    def __init__(self, status_code: int, *, headers=None, stream=None,\n"
    "                 content=None, text=None, html=None, json=None, request=None):\n"
    "        self.status_code = status_code\n"
    "        self.headers = Headers(headers)\n"
    "        self.stream = stream\n"
    "        self._request = request\n\n"
    "    @property\n"
    "    def text(self) -> str:\n"
    "        return self.content.decode(self.encoding)\n\n"
    "    def json(self, **kwargs) -> typing.Any:\n"
    "        return jsonlib.loads(self.text, **kwargs)\n\n"
    "    def raise_for_status(self) -> Response:\n"
    "        message = \"{} {}\".format(self.status_code, self.reason_phrase)\n"
    "        if self.is_client_error or self.is_server_error:\n"
    "            raise HTTPStatusError(message, request=self.request, response=self)\n"
    "        return self\n"
    "```\n"
)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for code symbols using vector similarity search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "top_k": {"type": "integer", "description": "Number of results", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code_with_graph",
            "description": "Hybrid search: vector similarity + graph expansion for related symbols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "vector_top_k": {"type": "integer", "default": 5},
                    "graph_hops": {"type": "integer", "default": 1},
                    "max_graph_nodes": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_symbol_source",
            "description": "Read the full source code of a specific code symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_name": {"type": "string", "description": "Name of the symbol to read"},
                },
                "required": ["symbol_name"],
            },
        },
    },
]


# --- Prompt categories ---

# Category 1: Simple Q&A (~50 input tokens, 150 output) - baseline
SIMPLE_QA = [
    {"messages": [{"role": "user", "content": "How does httpx handle authentication?"}], "max_tokens": 150, "category": "simple_qa"},
    {"messages": [{"role": "user", "content": "What is the Timeout class in httpx?"}], "max_tokens": 150, "category": "simple_qa"},
    {"messages": [{"role": "user", "content": "Show me how httpx handles redirects."}], "max_tokens": 150, "category": "simple_qa"},
    {"messages": [{"role": "user", "content": "How does connection pooling work in httpx?"}], "max_tokens": 150, "category": "simple_qa"},
    {"messages": [{"role": "user", "content": "What exceptions does httpx define?"}], "max_tokens": 150, "category": "simple_qa"},
]

# Category 2: RAG with retrieved context (~1500-2000 input tokens, 512 output)
RAG_QUERIES = [
    {
        "messages": [
            {"role": "system", "content": "You are a code assistant. Answer based on the retrieved code context below."},
            {"role": "user", "content": RETRIEVED_CONTEXT_AUTH + "\n\nQuestion: How does httpx handle authentication? Explain the auth flow mechanism, how different auth types are supported, and how the Client class wires them together."},
        ],
        "max_tokens": 512,
        "category": "rag",
    },
    {
        "messages": [
            {"role": "system", "content": "You are a code assistant. Answer based on the retrieved code context below."},
            {"role": "user", "content": RETRIEVED_CONTEXT_TRANSPORT + "\n\nQuestion: How does the transport layer work in httpx? Explain how Request and Response objects flow through HTTPTransport, and how the async variant differs."},
        ],
        "max_tokens": 512,
        "category": "rag",
    },
    {
        "messages": [
            {"role": "system", "content": "You are a code assistant. Answer based on the retrieved code context below."},
            {"role": "user", "content": RETRIEVED_CONTEXT_AUTH + "\n\nQuestion: Compare BasicAuth, DigestAuth, and NetRCAuth. What are the security implications of each? When would you use one over another?"},
        ],
        "max_tokens": 512,
        "category": "rag",
    },
    {
        "messages": [
            {"role": "system", "content": "You are a code assistant. Answer based on the retrieved code context below."},
            {"role": "user", "content": RETRIEVED_CONTEXT_TRANSPORT + "\n\nQuestion: How does httpx manage connection limits and keepalive? Trace the configuration from Limits through HTTPTransport to the underlying connection pool."},
        ],
        "max_tokens": 512,
        "category": "rag",
    },
]

# Category 3: Agent tool-calling (~500 input tokens with tools, 256 output)
AGENT_TOOL_CALLS = [
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_AGENT},
            {"role": "user", "content": "How does httpx handle SSL certificate verification? What parameters control this?"},
        ],
        "tools": TOOL_DEFINITIONS,
        "max_tokens": 256,
        "category": "agent_tool_call",
    },
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_AGENT},
            {"role": "user", "content": "Find all the exception classes in httpx and explain the hierarchy."},
        ],
        "tools": TOOL_DEFINITIONS,
        "max_tokens": 256,
        "category": "agent_tool_call",
    },
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_AGENT},
            {"role": "user", "content": "How does httpx implement streaming responses? Show me the relevant classes."},
        ],
        "tools": TOOL_DEFINITIONS,
        "max_tokens": 256,
        "category": "agent_tool_call",
    },
]

# Category 4: Multi-turn agent with tool results (~2500 input tokens, 512 output)
AGENT_MULTI_TURN = [
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_AGENT},
            {"role": "user", "content": "How does httpx handle authentication?"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "search_code_with_graph", "arguments": "{\"query\": \"authentication\", \"vector_top_k\": 5, \"graph_hops\": 1}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": (
                "Results:\n1. BasicAuth (class, httpx/_auth.py) - score: 0.92\n"
                "2. DigestAuth (class, httpx/_auth.py) - score: 0.89\n"
                "3. Auth (class, httpx/_auth.py) - score: 0.85 [graph]\n"
                "4. NetRCAuth (class, httpx/_auth.py) - score: 0.83\n"
                "5. FunctionAuth (class, httpx/_auth.py) - score: 0.80\n"
                "6. Client._build_auth (method, httpx/_client.py) - score: 0.75 [graph]\n"
                "7. BaseClient (class, httpx/_client.py) - score: 0.70 [graph]"
            )},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_2", "type": "function", "function": {"name": "read_symbol_source", "arguments": "{\"symbol_name\": \"Auth\"}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_2", "content": (
                "class Auth:\n"
                "    \"\"\"Base class for authentication.\"\"\"\n\n"
                "    requires_request_body = False\n"
                "    requires_response_body = False\n\n"
                "    def auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:\n"
                "        raise NotImplementedError()\n\n"
                "    def sync_auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:\n"
                "        yield from self.auth_flow(request)\n\n"
                "    async def async_auth_flow(self, request: Request) -> typing.AsyncGenerator[Request, Response]:\n"
                "        flow = self.auth_flow(request)\n"
                "        request = next(flow)\n"
                "        yield request\n"
                "        # ...\n"
            )},
            {"role": "user", "content": "Good, now synthesize everything you found. Explain the full authentication architecture."},
        ],
        "max_tokens": 1024,
        "category": "agent_multi_turn",
    },
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_AGENT},
            {"role": "user", "content": "How does httpx handle timeouts?"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "search_code", "arguments": "{\"query\": \"timeout configuration\"}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": (
                "Results:\n1. Timeout (class, httpx/_config.py) - score: 0.95\n"
                "2. TimeoutException (class, httpx/_exceptions.py) - score: 0.88\n"
                "3. ConnectTimeout (class, httpx/_exceptions.py) - score: 0.85\n"
                "4. ReadTimeout (class, httpx/_exceptions.py) - score: 0.83\n"
                "5. PoolTimeout (class, httpx/_exceptions.py) - score: 0.80"
            )},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_2", "type": "function", "function": {"name": "read_symbol_source", "arguments": "{\"symbol_name\": \"Timeout\"}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_2", "content": (
                "class Timeout:\n"
                "    \"\"\"Timeout configuration.\n\n"
                "    **Usage**:\n\n"
                "    Timeout(None)               # No timeouts.\n"
                "    Timeout(5.0)                # 5s timeout on all operations.\n"
                "    Timeout(None, connect=5.0)  # 5s timeout on connect, no other timeouts.\n"
                "    Timeout(5.0, connect=10.0)  # 10s timeout on connect. 5s timeout elsewhere.\n"
                "    Timeout(5.0, pool=None)     # No timeout on acquiring connection from pool.\n"
                "    \"\"\"\n\n"
                "    def __init__(self, timeout=UNSET, *, connect=UNSET, read=UNSET,\n"
                "                 write=UNSET, pool=UNSET):\n"
                "        if isinstance(timeout, Timeout):\n"
                "            self.connect = timeout.connect\n"
                "            self.read = timeout.read\n"
                "            self.write = timeout.write\n"
                "            self.pool = timeout.pool\n"
                "        else:\n"
                "            self.connect = connect if connect is not UNSET else timeout\n"
                "            self.read = read if read is not UNSET else timeout\n"
                "            self.write = write if write is not UNSET else timeout\n"
                "            self.pool = pool if pool is not UNSET else timeout\n"
            )},
            {"role": "user", "content": "Now explain the full timeout architecture — how timeouts propagate from config to the transport layer."},
        ],
        "max_tokens": 1024,
        "category": "agent_multi_turn",
    },
]

# Category 5: JSON extraction (~400 input tokens, 100 output)
JSON_EXTRACTION = [
    {
        "messages": [
            {"role": "user", "content": (
                "You are a code relationship extractor. Given two code symbols, determine their relationship.\n\n"
                "Symbol A:\n  Name: BasicAuth\n  Type: class\n  Source:\n```python\n"
                "class BasicAuth(Auth):\n    def __init__(self, username, password):\n"
                "        self._auth_header = self._build_auth_header(username, password)\n"
                "    def auth_flow(self, request):\n        request.headers['Authorization'] = self._auth_header\n"
                "        yield request\n```\n\n"
                "Symbol B:\n  Name: NetRCAuth\n  Type: class\n  Source:\n```python\n"
                "class NetRCAuth(Auth):\n    def __init__(self, file=None):\n"
                "        self._netrc_info = netrc.netrc(file)\n"
                "    def auth_flow(self, request):\n        auth_info = self._netrc_info.authenticators(request.url.host)\n"
                "        if auth_info:\n            request.headers['Authorization'] = self._build_auth_header(auth_info[0], auth_info[2])\n"
                "        yield request\n```\n\n"
                "Classify as SIMILAR_TO, DEPENDS_ON, or NONE.\n"
                "Respond with JSON only: {\"relationship\": \"<type>\", \"confidence\": <0.0-1.0>, \"reason\": \"<brief>\", \"direction\": \"A->B\" or \"B->A\" or \"bidirectional\"}"
            )},
        ],
        "max_tokens": 100,
        "category": "json_extraction",
    },
    {
        "messages": [
            {"role": "user", "content": (
                "You are a code relationship extractor. Given two code symbols, determine their relationship.\n\n"
                "Symbol A:\n  Name: HTTPTransport\n  Type: class\n  Source:\n```python\n"
                "class HTTPTransport(BaseTransport):\n    def __init__(self, verify=True, cert=None, http1=True, http2=False,\n"
                "                 limits=DEFAULT_LIMITS, trust_env=True):\n"
                "        self._pool = httpcore.ConnectionPool(ssl_context=ssl_context,\n"
                "            max_connections=limits.max_connections, http1=http1, http2=http2)\n"
                "    def handle_request(self, request):\n        resp = self._pool.handle_request(...)\n"
                "        return Response(status_code=resp.status, headers=resp.headers, stream=resp.stream)\n```\n\n"
                "Symbol B:\n  Name: AsyncHTTPTransport\n  Type: class\n  Source:\n```python\n"
                "class AsyncHTTPTransport(AsyncBaseTransport):\n    def __init__(self, verify=True, cert=None, http1=True, http2=False,\n"
                "                 limits=DEFAULT_LIMITS, trust_env=True):\n"
                "        self._pool = httpcore.AsyncConnectionPool(...)\n"
                "    async def handle_async_request(self, request):\n        resp = await self._pool.handle_async_request(...)\n"
                "        return Response(status_code=resp.status, ...)\n```\n\n"
                "Classify as SIMILAR_TO, DEPENDS_ON, or NONE.\n"
                "Respond with JSON only: {\"relationship\": \"<type>\", \"confidence\": <0.0-1.0>, \"reason\": \"<brief>\", \"direction\": \"A->B\" or \"B->A\" or \"bidirectional\"}"
            )},
        ],
        "max_tokens": 100,
        "category": "json_extraction",
    },
    {
        "messages": [
            {"role": "user", "content": (
                "You are evaluating a code retrieval system. Given a query and retrieved symbols, judge relevance.\n\n"
                "Query: How does httpx handle authentication?\n\n"
                "Retrieved symbols:\n"
                "1. class BasicAuth (httpx/_auth.py) - HTTP Basic authentication\n"
                "2. class DigestAuth (httpx/_auth.py) - HTTP Digest authentication\n"
                "3. class Limits (httpx/_config.py) - Connection pool limits configuration\n"
                "4. class Auth (httpx/_auth.py) - Base class for authentication\n"
                "5. method Client._build_auth (httpx/_client.py) - Build auth from auth parameter\n\n"
                "For each symbol, assign relevance: 3=essential, 2=important, 1=peripheral, 0=irrelevant.\n"
                "Respond with JSON array only:\n"
                "[{\"name\": \"<name>\", \"relevance\": <0-3>, \"reason\": \"<brief>\"}]"
            )},
        ],
        "max_tokens": 256,
        "category": "json_extraction",
    },
]

# Weight categories to approximate real workload distribution
ALL_PROMPTS = (
    SIMPLE_QA * 1           # 5 prompts  — ~15% of traffic
    + RAG_QUERIES * 2       # 8 prompts  — ~25% of traffic
    + AGENT_TOOL_CALLS * 2  # 6 prompts  — ~18% of traffic
    + AGENT_MULTI_TURN * 3  # 6 prompts  — ~18% of traffic
    + JSON_EXTRACTION * 3   # 9 prompts  — ~27% of traffic
)


class VLLMUser(HttpUser):
    """Simulates a user making LLM inference requests."""

    wait_time = between(0.5, 2.0)
    host = os.environ.get("VLLM_HOST", "http://localhost:8000")

    @task
    def chat_completion(self):
        prompt = random.choice(ALL_PROMPTS)
        category = prompt.get("category", "unknown")

        payload = {
            "model": MODEL,
            "messages": prompt["messages"],
            "max_tokens": prompt["max_tokens"],
            "temperature": 0.1,
        }

        if "tools" in prompt:
            payload["tools"] = prompt["tools"]

        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            catch_response=True,
            name=f"/v1/chat/completions [{category}]",
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    with _lock:
                        _token_counts["prompt"] += prompt_tokens
                        _token_counts["completion"] += completion_tokens

                    response.success()
                except Exception as e:
                    response.failure(f"JSON parse error: {e}")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text[:200]}")
