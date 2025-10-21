Source: https://langchain-ai.github.io/langgraph/concepts/streaming/

# Streaming

LangGraph implements a streaming system to surface real-time updates, allowing for responsive and transparent user experiences.

LangGraph’s streaming system lets you surface live feedback from graph runs to your app.  
There are three main categories of data you can stream:

1. **Workflow progress** — get state updates after each graph node is executed.
2. **LLM tokens** — stream language model tokens as they’re generated.
3. **Custom updates** — emit user-defined signals (e.g., “Fetched 10/100 records”).

## What’s possible with LangGraph streaming

- [**Stream LLM tokens**](../how-tos/streaming.md#messages) — capture token streams from anywhere: inside nodes, subgraphs, or tools.
- [**Emit progress notifications from tools**](../how-tos/streaming.md#stream-custom-data) — send custom updates or progress signals directly from tool functions.
- [**Stream from subgraphs**](../how-tos/streaming.md#stream-subgraph-outputs) — include outputs from both the parent graph and any nested subgraphs.
- [**Use any LLM**](../how-tos/streaming.md#use-with-any-llm) — stream tokens from any LLM, even if it's not a LangChain model using the `custom` streaming mode.
- [**Use multiple streaming modes**](../how-tos/streaming.md#stream-multiple-modes) — choose from `values` (full state), `updates` (state deltas), `messages` (LLM tokens + metadata), `custom` (arbitrary user data), or `debug` (detailed traces).

Source: https://langchain-ai.github.io/langgraph/concepts/persistence/

# Persistence

LangGraph has a built-in persistence layer, implemented through checkpointers. When you compile a graph with a checkpointer, the checkpointer saves a `checkpoint` of the graph state at every super-step. Those checkpoints are saved to a `thread`, which can be accessed after graph execution. Because `threads` allow access to graph's state after execution, several powerful capabilities including human-in-the-loop, memory, time travel, and fault-tolerance are all possible. Below, we'll discuss each of these concepts in more detail.

![Checkpoints](img/persistence/checkpoints.jpg)

!!! info "LangGraph API handles checkpointing automatically"

    When using the LangGraph API, you don't need to implement or configure checkpointers manually. The API handles all persistence infrastructure for you behind the scenes.

## Threads

A thread is a unique ID or thread identifier assigned to each checkpoint saved by a checkpointer. It contains the accumulated state of a sequence of [runs](./assistants.md#execution). When a run is executed, the [state](../concepts/low_level.md#state) of the underlying graph of the assistant will be persisted to the thread.

When invoking a graph with a checkpointer, you **must** specify a `thread_id` as part of the `configurable` portion of the config:

```python
{"configurable": {"thread_id": "1"}}
```





A thread's current and historical state can be retrieved. To persist state, a thread must be created prior to executing a run. The LangGraph Platform API provides several endpoints for creating and managing threads and thread state. See the [API reference](../cloud/reference/api/api_ref.html#tag/threads) for more details.

## Checkpoints

The state of a thread at a particular point in time is called a checkpoint. Checkpoint is a snapshot of the graph state saved at each super-step and is represented by `StateSnapshot` object with the following key properties:

- `config`: Config associated with this checkpoint.
- `metadata`: Metadata associated with this checkpoint.
- `values`: Values of the state channels at this point in time.
- `next` A tuple of the node names to execute next in the graph.
- `tasks`: A tuple of `PregelTask` objects that contain information about next tasks to be executed. If the step was previously attempted, it will include error information. If a graph was interrupted [dynamically](../how-tos/human_in_the_loop/add-human-in-the-loop.md#pause-using-interrupt) from within a node, tasks will contain additional data associated with interrupts.

Checkpoints are persisted and can be used to restore the state of a thread at a later time.

Let's see what checkpoints are saved when a simple graph is invoked as follows:

API Reference: StateGraph</a> | START</a> | END</a> | InMemorySaver</a></i></sup>

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]

def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}

def node_b(state: State):
    return {"foo": "b", "bar": ["b"]}


workflow = StateGraph(State)
workflow.add_node(node_a)
workflow.add_node(node_b)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", "node_b")
workflow.add_edge("node_b", END)

checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}
graph.invoke({"foo": ""}, config)
```







After we run the graph, we expect to see exactly 4 checkpoints:

- empty checkpoint with `START` as the next node to be executed
- checkpoint with the user input `{'foo': '', 'bar': []}` and `node_a` as the next node to be executed
- checkpoint with the outputs of `node_a` `{'foo': 'a', 'bar': ['a']}` and `node_b` as the next node to be executed
- checkpoint with the outputs of `node_b` `{'foo': 'b', 'bar': ['a', 'b']}` and no next nodes to be executed

Note that we `bar` channel values contain outputs from both nodes as we have a reducer for `bar` channel.





### Get state

When interacting with the saved graph state, you **must** specify a [thread identifier](#threads). You can view the _latest_ state of the graph by calling `graph.get_state(config)`. This will return a `StateSnapshot` object that corresponds to the latest checkpoint associated with the thread ID provided in the config or a checkpoint associated with a checkpoint ID for the thread, if provided.

```python
# get the latest state snapshot
config = {"configurable": {"thread_id": "1"}}
graph.get_state(config)

# get a state snapshot for a specific checkpoint_id
config = {"configurable": {"thread_id": "1", "checkpoint_id": "1ef663ba-28fe-6528-8002-5a559208592c"}}
graph.get_state(config)
```





In our example, the output of `get_state` will look like this:

```
StateSnapshot(
    values={'foo': 'b', 'bar': ['a', 'b']},
    next=(),
    config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28fe-6528-8002-5a559208592c'}},
    metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2},
    created_at='2024-08-29T19:19:38.821749+00:00',
    parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}}, tasks=()
)
```





### Get state history

You can get the full history of the graph execution for a given thread by calling `graph.get_state_history(config)`. This will return a list of `StateSnapshot` objects associated with the thread ID provided in the config. Importantly, the checkpoints will be ordered chronologically with the most recent checkpoint / `StateSnapshot` being the first in the list.

```python
config = {"configurable": {"thread_id": "1"}}
list(graph.get_state_history(config))
```





In our example, the output of `get_state_history` will look like this:

```
[
    StateSnapshot(
        values={'foo': 'b', 'bar': ['a', 'b']},
        next=(),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28fe-6528-8002-5a559208592c'}},
        metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2},
        created_at='2024-08-29T19:19:38.821749+00:00',
        parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}},
        tasks=(),
    ),
    StateSnapshot(
        values={'foo': 'a', 'bar': ['a']},
        next=('node_b',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}},
        metadata={'source': 'loop', 'writes': {'node_a': {'foo': 'a', 'bar': ['a']}}, 'step': 1},
        created_at='2024-08-29T19:19:38.819946+00:00',
        parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f4-6b4a-8000-ca575a13d36a'}},
        tasks=(PregelTask(id='6fb7314f-f114-5413-a1f3-d37dfe98ff44', name='node_b', error=None, interrupts=()),),
    ),
    StateSnapshot(
        values={'foo': '', 'bar': []},
        next=('node_a',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f4-6b4a-8000-ca575a13d36a'}},
        metadata={'source': 'loop', 'writes': None, 'step': 0},
        created_at='2024-08-29T19:19:38.817813+00:00',
        parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f0-6c66-bfff-6723431e8481'}},
        tasks=(PregelTask(id='f1b14528-5ee5-579c-949b-23ef9bfbed58', name='node_a', error=None, interrupts=()),),
    ),
    StateSnapshot(
        values={'bar': []},
        next=('__start__',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f0-6c66-bfff-6723431e8481'}},
        metadata={'source': 'input', 'writes': {'foo': ''}, 'step': -1},
        created_at='2024-08-29T19:19:38.816205+00:00',
        parent_config=None,
        tasks=(PregelTask(id='6d27aa2e-d72b-5504-a36f-8620e54a76dd', name='__start__', error=None, interrupts=()),),
    )
]
```





![State](img/persistence/get_state.jpg)

### Replay

It's also possible to play-back a prior graph execution. If we `invoke` a graph with a `thread_id` and a `checkpoint_id`, then we will _re-play_ the previously executed steps _before_ a checkpoint that corresponds to the `checkpoint_id`, and only execute the steps _after_ the checkpoint.

- `thread_id` is the ID of a thread.
- `checkpoint_id` is an identifier that refers to a specific checkpoint within a thread.

You must pass these when invoking the graph as part of the `configurable` portion of the config:

```python
config = {"configurable": {"thread_id": "1", "checkpoint_id": "0c62ca34-ac19-445d-bbb0-5b4984975b2a"}}
graph.invoke(None, config=config)
```





Importantly, LangGraph knows whether a particular step has been executed previously. If it has, LangGraph simply _re-plays_ that particular step in the graph and does not re-execute the step, but only for the steps _before_ the provided `checkpoint_id`. All of the steps _after_ `checkpoint_id` will be executed (i.e., a new fork), even if they have been executed previously. See this [how to guide on time-travel to learn more about replaying](../how-tos/human_in_the_loop/time-travel.md).

![Replay](img/persistence/re_play.png)

### Update state

In addition to re-playing the graph from specific `checkpoints`, we can also _edit_ the graph state. We do this using `graph.update_state()`. This method accepts three different arguments:





#### `config`

The config should contain `thread_id` specifying which thread to update. When only the `thread_id` is passed, we update (or fork) the current state. Optionally, if we include `checkpoint_id` field, then we fork that selected checkpoint.

#### `values`

These are the values that will be used to update the state. Note that this update is treated exactly as any update from a node is treated. This means that these values will be passed to the [reducer](./low_level.md#reducers) functions, if they are defined for some of the channels in the graph state. This means that `update_state` does NOT automatically overwrite the channel values for every channel, but only for the channels without reducers. Let's walk through an example.

Let's assume you have defined the state of your graph with the following schema (see full example above):

```python
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    foo: int
    bar: Annotated[list[str], add]
```





Let's now assume the current state of the graph is

```
{"foo": 1, "bar": ["a"]}
```





If you update the state as below:

```python
graph.update_state(config, {"foo": 2, "bar": ["b"]})
```





Then the new state of the graph will be:

```
{"foo": 2, "bar": ["a", "b"]}
```

The `foo` key (channel) is completely changed (because there is no reducer specified for that channel, so `update_state` overwrites it). However, there is a reducer specified for the `bar` key, and so it appends `"b"` to the state of `bar`.




#### `as_node`

The final thing you can optionally specify when calling `update_state` is `as_node`. If you provided it, the update will be applied as if it came from node `as_node`. If `as_node` is not provided, it will be set to the last node that updated the state, if not ambiguous. The reason this matters is that the next steps to execute depend on the last node to have given an update, so this can be used to control which node executes next. See this [how to guide on time-travel to learn more about forking state](../how-tos/human_in_the_loop/time-travel.md).




![Update](img/persistence/checkpoints_full_story.jpg)

## Memory Store

![Model of shared state](img/persistence/shared_state.png)

A [state schema](low_level.md#schema) specifies a set of keys that are populated as a graph is executed. As discussed above, state can be written by a checkpointer to a thread at each graph step, enabling state persistence.

But, what if we want to retain some information _across threads_? Consider the case of a chatbot where we want to retain specific information about the user across _all_ chat conversations (e.g., threads) with that user!

With checkpointers alone, we cannot share information across threads. This motivates the need for the [`Store`](../reference/store.md#langgraph.store.base.BaseStore) interface. As an illustration, we can define an `InMemoryStore` to store information about a user across threads. We simply compile our graph with a checkpointer, as before, and with our new `in_memory_store` variable.

!!! info "LangGraph API handles stores automatically"

    When using the LangGraph API, you don't need to implement or configure stores manually. The API handles all storage infrastructure for you behind the scenes.

### Basic Usage

First, let's showcase this in isolation without using LangGraph.

```python
from langgraph.store.memory import InMemoryStore
in_memory_store = InMemoryStore()
```





Memories are namespaced by a `tuple`, which in this specific example will be `(, "memories")`. The namespace can be any length and represent anything, does not have to be user specific.

```python
user_id = "1"
namespace_for_memory = (user_id, "memories")
```





We use the `store.put` method to save memories to our namespace in the store. When we do this, we specify the namespace, as defined above, and a key-value pair for the memory: the key is simply a unique identifier for the memory (`memory_id`) and the value (a dictionary) is the memory itself.

```python
memory_id = str(uuid.uuid4())
memory = {"food_preference" : "I like pizza"}
in_memory_store.put(namespace_for_memory, memory_id, memory)
```





We can read out memories in our namespace using the `store.search` method, which will return all memories for a given user as a list. The most recent memory is the last in the list.

```python
memories = in_memory_store.search(namespace_for_memory)
memories[-1].dict()
{'value': {'food_preference': 'I like pizza'},
 'key': '07e0caf4-1631-47b7-b15f-65515d4c1843',
 'namespace': ['1', 'memories'],
 'created_at': '2024-10-02T17:22:31.590602+00:00',
 'updated_at': '2024-10-02T17:22:31.590605+00:00'}
```

Each memory type is a Python class ([`Item`](https://langchain-ai.github.io/langgraph/reference/store/#langgraph.store.base.Item)) with certain attributes. We can access it as a dictionary by converting via `.dict` as above.

The attributes it has are:

- `value`: The value (itself a dictionary) of this memory
- `key`: A unique key for this memory in this namespace
- `namespace`: A list of strings, the namespace of this memory type
- `created_at`: Timestamp for when this memory was created
- `updated_at`: Timestamp for when this memory was updated





### Semantic Search

Beyond simple retrieval, the store also supports semantic search, allowing you to find memories based on meaning rather than exact matches. To enable this, configure the store with an embedding model:

API Reference: init_embeddings</a></i></sup>

```python
from langchain.embeddings import init_embeddings

store = InMemoryStore(
    index={
        "embed": init_embeddings("openai:text-embedding-3-small"),  # Embedding provider
        "dims": 1536,                              # Embedding dimensions
        "fields": ["food_preference", "$"]              # Fields to embed
    }
)
```





Now when searching, you can use natural language queries to find relevant memories:

```python
# Find memories about food preferences
# (This can be done after putting memories into the store)
memories = store.search(
    namespace_for_memory,
    query="What does the user like to eat?",
    limit=3  # Return top 3 matches
)
```





You can control which parts of your memories get embedded by configuring the `fields` parameter or by specifying the `index` parameter when storing memories:

```python
# Store with specific fields to embed
store.put(
    namespace_for_memory,
    str(uuid.uuid4()),
    {
        "food_preference": "I love Italian cuisine",
        "context": "Discussing dinner plans"
    },
    index=["food_preference"]  # Only embed "food_preferences" field
)

# Store without embedding (still retrievable, but not searchable)
store.put(
    namespace_for_memory,
    str(uuid.uuid4()),
    {"system_info": "Last updated: 2024-01-01"},
    index=False
)
```





### Using in LangGraph

With this all in place, we use the `in_memory_store` in LangGraph. The `in_memory_store` works hand-in-hand with the checkpointer: the checkpointer saves state to threads, as discussed above, and the `in_memory_store` allows us to store arbitrary information for access _across_ threads. We compile the graph with both the checkpointer and the `in_memory_store` as follows.

API Reference: InMemorySaver</a></i></sup>

```python
from langgraph.checkpoint.memory import InMemorySaver

# We need this because we want to enable threads (conversations)
checkpointer = InMemorySaver()

# ... Define the graph ...

# Compile the graph with the checkpointer and store
graph = graph.compile(checkpointer=checkpointer, store=in_memory_store)
```





We invoke the graph with a `thread_id`, as before, and also with a `user_id`, which we'll use to namespace our memories to this particular user as we showed above.

```python
# Invoke the graph
user_id = "1"
config = {"configurable": {"thread_id": "1", "user_id": user_id}}

# First let's just say hi to the AI
for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi"}]}, config, stream_mode="updates"
):
    print(update)
```





We can access the `in_memory_store` and the `user_id` in _any node_ by passing `store: BaseStore` and `config: RunnableConfig` as node arguments. Here's how we might use semantic search in a node to find relevant memories:

```python
def update_memory(state: MessagesState, config: RunnableConfig, *, store: BaseStore):

    # Get the user id from the config
    user_id = config["configurable"]["user_id"]

    # Namespace the memory
    namespace = (user_id, "memories")

    # ... Analyze conversation and create a new memory

    # Create a new memory ID
    memory_id = str(uuid.uuid4())

    # We create a new memory
    store.put(namespace, memory_id, {"memory": memory})

```





As we showed above, we can also access the store in any node and use the `store.search` method to get memories. Recall the memories are returned as a list of objects that can be converted to a dictionary.

```python
memories[-1].dict()
{'value': {'food_preference': 'I like pizza'},
 'key': '07e0caf4-1631-47b7-b15f-65515d4c1843',
 'namespace': ['1', 'memories'],
 'created_at': '2024-10-02T17:22:31.590602+00:00',
 'updated_at': '2024-10-02T17:22:31.590605+00:00'}
```





We can access the memories and use them in our model call.

```python
def call_model(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    # Get the user id from the config
    user_id = config["configurable"]["user_id"]

    # Namespace the memory
    namespace = (user_id, "memories")

    # Search based on the most recent message
    memories = store.search(
        namespace,
        query=state["messages"][-1].content,
        limit=3
    )
    info = "\n".join([d.value["memory"] for d in memories])

    # ... Use memories in the model call
```





If we create a new thread, we can still access the same memories so long as the `user_id` is the same.

```python
# Invoke the graph
config = {"configurable": {"thread_id": "2", "user_id": "1"}}

# Let's say hi again
for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi, tell me about my memories"}]}, config, stream_mode="updates"
):
    print(update)
```





When we use the LangGraph Platform, either locally (e.g., in LangGraph Studio) or with LangGraph Platform, the base store is available to use by default and does not need to be specified during graph compilation. To enable semantic search, however, you **do** need to configure the indexing settings in your `langgraph.json` file. For example:

```json
{
    ...
    "store": {
        "index": {
            "embed": "openai:text-embeddings-3-small",
            "dims": 1536,
            "fields": ["$"]
        }
    }
}
```

See the [deployment guide](../cloud/deployment/semantic_search.md) for more details and configuration options.

## Checkpointer libraries

Under the hood, checkpointing is powered by checkpointer objects that conform to [BaseCheckpointSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.base.BaseCheckpointSaver) interface. LangGraph provides several checkpointer implementations, all implemented via standalone, installable libraries:

- `langgraph-checkpoint`: The base interface for checkpointer savers ([BaseCheckpointSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.base.BaseCheckpointSaver)) and serialization/deserialization interface ([SerializerProtocol](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.serde.base.SerializerProtocol)). Includes in-memory checkpointer implementation ([InMemorySaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.memory.InMemorySaver)) for experimentation. LangGraph comes with `langgraph-checkpoint` included.
- `langgraph-checkpoint-sqlite`: An implementation of LangGraph checkpointer that uses SQLite database ([SqliteSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.sqlite.SqliteSaver) / [AsyncSqliteSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver)). Ideal for experimentation and local workflows. Needs to be installed separately.
- `langgraph-checkpoint-postgres`: An advanced checkpointer that uses Postgres database ([PostgresSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.postgres.PostgresSaver) / [AsyncPostgresSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.postgres.aio.AsyncPostgresSaver)), used in LangGraph Platform. Ideal for using in production. Needs to be installed separately.





### Checkpointer interface

Each checkpointer conforms to [BaseCheckpointSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.base.BaseCheckpointSaver) interface and implements the following methods:

- `.put` - Store a checkpoint with its configuration and metadata.
- `.put_writes` - Store intermediate writes linked to a checkpoint (i.e. [pending writes](#pending-writes)).
- `.get_tuple` - Fetch a checkpoint tuple using for a given configuration (`thread_id` and `checkpoint_id`). This is used to populate `StateSnapshot` in `graph.get_state()`.
- `.list` - List checkpoints that match a given configuration and filter criteria. This is used to populate state history in `graph.get_state_history()`

If the checkpointer is used with asynchronous graph execution (i.e. executing the graph via `.ainvoke`, `.astream`, `.abatch`), asynchronous versions of the above methods will be used (`.aput`, `.aput_writes`, `.aget_tuple`, `.alist`).

!!! note

    For running your graph asynchronously, you can use `InMemorySaver`, or async versions of Sqlite/Postgres checkpointers -- `AsyncSqliteSaver` / `AsyncPostgresSaver` checkpointers.





### Serializer

When checkpointers save the graph state, they need to serialize the channel values in the state. This is done using serializer objects.

`langgraph_checkpoint` defines [protocol](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.serde.base.SerializerProtocol) for implementing serializers provides a default implementation ([JsonPlusSerializer](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer)) that handles a wide variety of types, including LangChain and LangGraph primitives, datetimes, enums and more.

#### Serialization with `pickle`

The default serializer, [`JsonPlusSerializer`](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer), uses ormsgpack and JSON under the hood, which is not suitable for all types of objects.

If you want to fallback to pickle for objects not currently supported by our msgpack encoder (such as Pandas dataframes),
you can use the `pickle_fallback` argument of the `JsonPlusSerializer`:

API Reference: InMemorySaver</a> | JsonPlusSerializer</a></i></sup>

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# ... Define the graph ...
graph.compile(
    checkpointer=InMemorySaver(serde=JsonPlusSerializer(pickle_fallback=True))
)
```

#### Encryption

Checkpointers can optionally encrypt all persisted state. To enable this, pass an instance of [`EncryptedSerializer`](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.serde.encrypted.EncryptedSerializer) to the `serde` argument of any `BaseCheckpointSaver` implementation. The easiest way to create an encrypted serializer is via [`from_pycryptodome_aes`](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.serde.encrypted.EncryptedSerializer.from_pycryptodome_aes), which reads the AES key from the `LANGGRAPH_AES_KEY` environment variable (or accepts a `key` argument):

API Reference: SqliteSaver</a></i></sup>

```python
import sqlite3

from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

serde = EncryptedSerializer.from_pycryptodome_aes()  # reads LANGGRAPH_AES_KEY
checkpointer = SqliteSaver(sqlite3.connect("checkpoint.db"), serde=serde)
```

API Reference: PostgresSaver</a></i></sup>

```python
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.postgres import PostgresSaver

serde = EncryptedSerializer.from_pycryptodome_aes()
checkpointer = PostgresSaver.from_conn_string("postgresql://...", serde=serde)
checkpointer.setup()
```

When running on LangGraph Platform, encryption is automatically enabled whenever `LANGGRAPH_AES_KEY` is present, so you only need to provide the environment variable. Other encryption schemes can be used by implementing [`CipherProtocol`](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.serde.base.CipherProtocol) and supplying it to `EncryptedSerializer`.




## Capabilities

### Human-in-the-loop

First, checkpointers facilitate [human-in-the-loop workflows](agentic_concepts.md#human-in-the-loop) workflows by allowing humans to inspect, interrupt, and approve graph steps. Checkpointers are needed for these workflows as the human has to be able to view the state of a graph at any point in time, and the graph has to be to resume execution after the human has made any updates to the state. See [the how-to guides](../how-tos/human_in_the_loop/add-human-in-the-loop.md) for examples.

### Memory

Second, checkpointers allow for ["memory"](../concepts/memory.md) between interactions. In the case of repeated human interactions (like conversations) any follow up messages can be sent to that thread, which will retain its memory of previous ones. See [Add memory](../how-tos/memory/add-memory.md) for information on how to add and manage conversation memory using checkpointers.

### Time Travel

Third, checkpointers allow for ["time travel"](time-travel.md), allowing users to replay prior graph executions to review and / or debug specific graph steps. In addition, checkpointers make it possible to fork the graph state at arbitrary checkpoints to explore alternative trajectories.

### Fault-tolerance

Lastly, checkpointing also provides fault-tolerance and error recovery: if one or more nodes fail at a given superstep, you can restart your graph from the last successful step. Additionally, when a graph node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from any other nodes that completed successfully at that superstep, so that whenever we resume graph execution from that superstep we don't re-run the successful nodes.

#### Pending writes

Additionally, when a graph node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from any other nodes that completed successfully at that superstep, so that whenever we resume graph execution from that superstep we don't re-run the successful nodes.

Source: https://langchain-ai.github.io/langgraph/concepts/durable_execution/

# Durable Execution

**Durable execution** is a technique in which a process or workflow saves its progress at key points, allowing it to pause and later resume exactly where it left off. This is particularly useful in scenarios that require [human-in-the-loop](./human_in_the_loop.md), where users can inspect, validate, or modify the process before continuing, and in long-running tasks that might encounter interruptions or errors (e.g., calls to an LLM timing out). By preserving completed work, durable execution enables a process to resume without reprocessing previous steps -- even after a significant delay (e.g., a week later).

LangGraph's built-in [persistence](./persistence.md) layer provides durable execution for workflows, ensuring that the state of each execution step is saved to a durable store. This capability guarantees that if a workflow is interrupted -- whether by a system failure or for [human-in-the-loop](./human_in_the_loop.md) interactions -- it can be resumed from its last recorded state.

!!! tip

    If you are using LangGraph with a checkpointer, you already have durable execution enabled. You can pause and resume workflows at any point, even after interruptions or failures.
    To make the most of durable execution, ensure that your workflow is designed to be [deterministic](#determinism-and-consistent-replay) and [idempotent](#determinism-and-consistent-replay) and wrap any side effects or non-deterministic operations inside [tasks](./functional_api.md#task). You can use [tasks](./functional_api.md#task) from both the [StateGraph (Graph API)](./low_level.md) and the [Functional API](./functional_api.md).

## Requirements

To leverage durable execution in LangGraph, you need to:

1. Enable [persistence](./persistence.md) in your workflow by specifying a [checkpointer](./persistence.md#checkpointer-libraries) that will save workflow progress.
2. Specify a [thread identifier](./persistence.md#threads) when executing a workflow. This will track the execution history for a particular instance of the workflow.

3. Wrap any non-deterministic operations (e.g., random number generation) or operations with side effects (e.g., file writes, API calls) inside [tasks](https://langchain-ai.github.io/langgraph/reference/func/#langgraph.func.task) to ensure that when a workflow is resumed, these operations are not repeated for the particular run, and instead their results are retrieved from the persistence layer. For more information, see [Determinism and Consistent Replay](#determinism-and-consistent-replay).




## Determinism and Consistent Replay

When you resume a workflow run, the code does **NOT** resume from the **same line of code** where execution stopped; instead, it will identify an appropriate [starting point](#starting-points-for-resuming-workflows) from which to pick up where it left off. This means that the workflow will replay all steps from the [starting point](#starting-points-for-resuming-workflows) until it reaches the point where it was stopped.

As a result, when you are writing a workflow for durable execution, you must wrap any non-deterministic operations (e.g., random number generation) and any operations with side effects (e.g., file writes, API calls) inside [tasks](./functional_api.md#task) or [nodes](./low_level.md#nodes).

To ensure that your workflow is deterministic and can be consistently replayed, follow these guidelines:

- **Avoid Repeating Work**: If a [node](./low_level.md#nodes) contains multiple operations with side effects (e.g., logging, file writes, or network calls), wrap each operation in a separate **task**. This ensures that when the workflow is resumed, the operations are not repeated, and their results are retrieved from the persistence layer.
- **Encapsulate Non-Deterministic Operations:** Wrap any code that might yield non-deterministic results (e.g., random number generation) inside **tasks** or **nodes**. This ensures that, upon resumption, the workflow follows the exact recorded sequence of steps with the same outcomes.
- **Use Idempotent Operations**: When possible ensure that side effects (e.g., API calls, file writes) are idempotent. This means that if an operation is retried after a failure in the workflow, it will have the same effect as the first time it was executed. This is particularly important for operations that result in data writes. In the event that a **task** starts but fails to complete successfully, the workflow's resumption will re-run the **task**, relying on recorded outcomes to maintain consistency. Use idempotency keys or verify existing results to avoid unintended duplication, ensuring a smooth and predictable workflow execution.

For some examples of pitfalls to avoid, see the [Common Pitfalls](./functional_api.md#common-pitfalls) section in the functional API, which shows
how to structure your code using **tasks** to avoid these issues. The same principles apply to the [StateGraph (Graph API)](https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.StateGraph).




## Durability modes

LangGraph supports three durability modes that allow you to balance performance and data consistency based on your application's requirements. The durability modes, from least to most durable, are as follows:

- [`"exit"`](#exit)
- [`"async"`](#async)
- [`"sync"`](#sync)

A higher durability mode add more overhead to the workflow execution.

!!! version-added "Added in v0.6.0"

    Use the `durability` parameter instead of `checkpoint_during` (deprecated in v0.6.0) for persistence policy management:
    
    * `durability="async"` replaces `checkpoint_during=True`
    * `durability="exit"` replaces `checkpoint_during=False`
    
    for persistence policy management, with the following mapping:

    * `checkpoint_during=True` -> `durability="async"`
    * `checkpoint_during=False` -> `durability="exit"`


### `"exit"`
Changes are persisted only when graph execution completes (either successfully or with an error). This provides the best performance for long-running graphs but means intermediate state is not saved, so you cannot recover from mid-execution failures or interrupt the graph execution.

### `"async"`
Changes are persisted asynchronously while the next step executes. This provides good performance and durability, but there's a small risk that checkpoints might not be written if the process crashes during execution.

### `"sync"`
Changes are persisted synchronously before the next step starts. This ensures that every checkpoint is written before continuing execution, providing high durability at the cost of some performance overhead.

You can specify the durability mode when calling any graph execution method:

```python
graph.stream(
    {"input": "test"}, 
    durability="sync"
)
```



## Using tasks in nodes

If a [node](./low_level.md#nodes) contains multiple operations, you may find it easier to convert each operation into a **task** rather than refactor the operations into individual nodes.

=== "Original"

    ```python hl_lines="16"
    from typing import NotRequired
    from typing_extensions import TypedDict
    import uuid

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import StateGraph, START, END
    import requests

    # Define a TypedDict to represent the state
    class State(TypedDict):
        url: str
        result: NotRequired[str]

    def call_api(state: State):
        """Example node that makes an API request."""
        result = requests.get(state['url']).text[:100]  # Side-effect
        return {
            "result": result
        }

    # Create a StateGraph builder and add a node for the call_api function
    builder = StateGraph(State)
    builder.add_node("call_api", call_api)

    # Connect the start and end nodes to the call_api node
    builder.add_edge(START, "call_api")
    builder.add_edge("call_api", END)

    # Specify a checkpointer
    checkpointer = InMemorySaver()

    # Compile the graph with the checkpointer
    graph = builder.compile(checkpointer=checkpointer)

    # Define a config with a thread ID.
    thread_id = uuid.uuid4()
    config = {"configurable": {"thread_id": thread_id}}

    # Invoke the graph
    graph.invoke({"url": "https://www.example.com"}, config)
    ```

=== "With task"

    ```python hl_lines="19 23"
    from typing import NotRequired
    from typing_extensions import TypedDict
    import uuid

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.func import task
    from langgraph.graph import StateGraph, START, END
    import requests

    # Define a TypedDict to represent the state
    class State(TypedDict):
        urls: list[str]
        result: NotRequired[list[str]]


    @task
    def _make_request(url: str):
        """Make a request."""
        return requests.get(url).text[:100]

    def call_api(state: State):
        """Example node that makes an API request."""
        requests = [_make_request(url) for url in state['urls']]
        results = [request.result() for request in requests]
        return {
            "results": results
        }

    # Create a StateGraph builder and add a node for the call_api function
    builder = StateGraph(State)
    builder.add_node("call_api", call_api)

    # Connect the start and end nodes to the call_api node
    builder.add_edge(START, "call_api")
    builder.add_edge("call_api", END)

    # Specify a checkpointer
    checkpointer = InMemorySaver()

    # Compile the graph with the checkpointer
    graph = builder.compile(checkpointer=checkpointer)

    # Define a config with a thread ID.
    thread_id = uuid.uuid4()
    config = {"configurable": {"thread_id": thread_id}}

    # Invoke the graph
    graph.invoke({"urls": ["https://www.example.com"]}, config)
    ```





## Resuming Workflows

Once you have enabled durable execution in your workflow, you can resume execution for the following scenarios:

- **Pausing and Resuming Workflows:** Use the [interrupt](https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.Interrupt) function to pause a workflow at specific points and the [Command](https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.Command) primitive to resume it with updated state. See [**Human-in-the-Loop**](./human_in_the_loop.md) for more details.
- **Recovering from Failures:** Automatically resume workflows from the last successful checkpoint after an exception (e.g., LLM provider outage). This involves executing the workflow with the same thread identifier by providing it with a `None` as the input value (see this [example](../how-tos/use-functional-api.md#resuming-after-an-error) with the functional API).




## Starting Points for Resuming Workflows

- If you're using a [StateGraph (Graph API)](https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.StateGraph), the starting point is the beginning of the [**node**](./low_level.md#nodes) where execution stopped.
- If you're making a subgraph call inside a node, the starting point will be the **parent** node that called the subgraph that was halted.
  Inside the subgraph, the starting point will be the specific [**node**](./low_level.md#nodes) where execution stopped.
- If you're using the Functional API, the starting point is the beginning of the [**entrypoint**](./functional_api.md#entrypoint) where execution stopped.


Source: https://langchain-ai.github.io/langgraph/concepts/memory/

# Memory

[Memory](../how-tos/memory/add-memory.md) is a system that remembers information about previous interactions. For AI agents, memory is crucial because it lets them remember previous interactions, learn from feedback, and adapt to user preferences. As agents tackle more complex tasks with numerous user interactions, this capability becomes essential for both efficiency and user satisfaction.

This conceptual guide covers two types of memory, based on their recall scope:

- [Short-term memory](#short-term-memory), or [thread](persistence.md#threads)-scoped memory, tracks the ongoing conversation by maintaining message history within a session. LangGraph manages short-term memory as a part of your agent's [state](low_level.md#state). State is persisted to a database using a [checkpointer](persistence.md#checkpoints) so the thread can be resumed at any time. Short-term memory updates when the graph is invoked or a step is completed, and the State is read at the start of each step.

- [Long-term memory](#long-term-memory) stores user-specific or application-level data across sessions and is shared _across_ conversational threads. It can be recalled _at any time_ and _in any thread_. Memories are scoped to any custom namespace, not just within a single thread ID. LangGraph provides [stores](persistence.md#memory-store) ([reference doc](https://langchain-ai.github.io/langgraph/reference/store/#langgraph.store.base.BaseStore)) to let you save and recall long-term memories.

![](img/memory/short-vs-long.png)


## Short-term memory

[Short-term memory](../how-tos/memory/add-memory.md#add-short-term-memory) lets your application remember previous interactions within a single [thread](persistence.md#threads) or conversation. A [thread](persistence.md#threads) organizes multiple interactions in a session, similar to the way email groups messages in a single conversation.

LangGraph manages short-term memory as part of the agent's state, persisted via thread-scoped checkpoints. This state can normally include the conversation history along with other stateful data, such as uploaded files, retrieved documents, or generated artifacts. By storing these in the graph's state, the bot can access the full context for a given conversation while maintaining separation between different threads.

### Manage short-term memory

Conversation history is the most common form of short-term memory, and long conversations pose a challenge to today's LLMs. A full history may not fit inside an LLM's context window, resulting in an irrecoverable error. Even if your LLM supports the full context length, most LLMs still perform poorly over long contexts. They get "distracted" by stale or off-topic content, all while suffering from slower response times and higher costs.

Chat models accept context using messages, which include developer provided instructions (a system message) and user inputs (human messages). In chat applications, messages alternate between human inputs and model responses, resulting in a list of messages that grows longer over time. Because context windows are limited and token-rich message lists can be costly, many applications can benefit from using techniques to manually remove or forget stale information.

![](img/memory/filter.png)

For more information on common techniques for managing messages, see the [Add and manage memory](../how-tos/memory/add-memory.md#manage-short-term-memory) guide.

## Long-term memory

[Long-term memory](../how-tos/memory/add-memory.md#add-long-term-memory) in LangGraph allows systems to retain information across different conversations or sessions. Unlike short-term memory, which is **thread-scoped**, long-term memory is saved within custom "namespaces."

Long-term memory is a complex challenge without a one-size-fits-all solution. However, the following questions provide a framework to help you navigate the different techniques:

- [What is the type of memory?](#memory-types) Humans use memories to remember facts ([semantic memory](#semantic-memory)), experiences ([episodic memory](#episodic-memory)), and rules ([procedural memory](#procedural-memory)). AI agents can use memory in the same ways. For example, AI agents can use memory to remember specific facts about a user to accomplish a task.

- [When do you want to update memories?](#writing-memories) Memory can be updated as part of an agent's application logic (e.g., "on the hot path"). In this case, the agent typically decides to remember facts before responding to a user. Alternatively, memory can be updated as a background task (logic that runs in the background / asynchronously and generates memories). We explain the tradeoffs between these approaches in the [section below](#writing-memories).

### Memory types

Different applications require various types of memory. Although the analogy isn't perfect, examining [human memory types](https://www.psychologytoday.com/us/basics/memory/types-of-memory?ref=blog.langchain.dev) can be insightful. Some research (e.g., the [CoALA paper](https://arxiv.org/pdf/2309.02427)) have even mapped these human memory types to those used in AI agents.

| Memory Type | What is Stored | Human Example | Agent Example |
|-------------|----------------|---------------|---------------|
| [Semantic](#semantic-memory) | Facts | Things I learned in school | Facts about a user |
| [Episodic](#episodic-memory) | Experiences | Things I did | Past agent actions |
| [Procedural](#procedural-memory) | Instructions | Instincts or motor skills | Agent system prompt |

#### Semantic memory

[Semantic memory](https://en.wikipedia.org/wiki/Semantic_memory), both in humans and AI agents, involves the retention of specific facts and concepts. In humans, it can include information learned in school and the understanding of concepts and their relationships. For AI agents, semantic memory is often used to personalize applications by remembering facts or concepts from past interactions. 

!!! note

    Semantic memory is different from "semantic search," which is a technique for finding similar content using "meaning" (usually as embeddings). Semantic memory is a term from psychology, referring to storing facts and knowledge, while semantic search is a method for retrieving information based on meaning rather than exact matches.


##### Profile

Semantic memories can be managed in different ways. For example, memories can be a single, continuously updated "profile" of well-scoped and specific information about a user, organization, or other entity (including the agent itself). A profile is generally just a JSON document with various key-value pairs you've selected to represent your domain. 

When remembering a profile, you will want to make sure that you are **updating** the profile each time. As a result, you will want to pass in the previous profile and [ask the model to generate a new profile](https://github.com/langchain-ai/memory-template) (or some [JSON patch](https://github.com/hinthornw/trustcall) to apply to the old profile). This can be become error-prone as the profile gets larger, and may benefit from splitting a profile into multiple documents or **strict** decoding when generating documents to ensure the memory schemas remains valid.

![](img/memory/update-profile.png)

##### Collection

Alternatively, memories can be a collection of documents that are continuously updated and extended over time. Each individual memory can be more narrowly scoped and easier to generate, which means that you're less likely to **lose** information over time. It's easier for an LLM to generate _new_ objects for new information than reconcile new information with an existing profile. As a result, a document collection tends to lead to [higher recall downstream](https://en.wikipedia.org/wiki/Precision_and_recall).

However, this shifts some complexity memory updating. The model must now _delete_ or _update_ existing items in the list, which can be tricky. In addition, some models may default to over-inserting and others may default to over-updating. See the [Trustcall](https://github.com/hinthornw/trustcall) package for one way to manage this and consider evaluation (e.g., with a tool like [LangSmith](https://docs.smith.langchain.com/tutorials/Developers/evaluation)) to help you tune the behavior.

Working with document collections also shifts complexity to memory **search** over the list. The `Store` currently supports both [semantic search](https://langchain-ai.github.io/langgraph/reference/store/#langgraph.store.base.SearchOp.query) and [filtering by content](https://langchain-ai.github.io/langgraph/reference/store/#langgraph.store.base.SearchOp.filter).

Finally, using a collection of memories can make it challenging to provide comprehensive context to the model. While individual memories may follow a specific schema, this structure might not capture the full context or relationships between memories. As a result, when using these memories to generate responses, the model may lack important contextual information that would be more readily available in a unified profile approach.

![](img/memory/update-list.png)

Regardless of memory management approach, the central point is that the agent will use the semantic memories to [ground its responses](https://python.langchain.com/docs/concepts/rag/), which often leads to more personalized and relevant interactions.

#### Episodic memory

[Episodic memory](https://en.wikipedia.org/wiki/Episodic_memory), in both humans and AI agents, involves recalling past events or actions. The [CoALA paper](https://arxiv.org/pdf/2309.02427) frames this well: facts can be written to semantic memory, whereas *experiences* can be written to episodic memory. For AI agents, episodic memory is often used to help an agent remember how to accomplish a task. 

In practice, episodic memories are often implemented through [few-shot example prompting](https://python.langchain.com/docs/concepts/few_shot_prompting/), where agents learn from past sequences to perform tasks correctly. Sometimes it's easier to "show" than "tell" and LLMs learn well from examples. Few-shot learning lets you ["program"](https://x.com/karpathy/status/1627366413840322562) your LLM by updating the prompt with input-output examples to illustrate the intended behavior. While various [best-practices](https://python.langchain.com/docs/concepts/#1-generating-examples) can be used to generate few-shot examples, often the challenge lies in selecting the most relevant examples based on user input.




Note that the memory [store](persistence.md#memory-store) is just one way to store data as few-shot examples. If you want to have more developer involvement, or tie few-shots more closely to your evaluation harness, you can also use a [LangSmith Dataset](https://docs.smith.langchain.com/evaluation/how_to_guides/datasets/index_datasets_for_dynamic_few_shot_example_selection) to store your data. Then dynamic few-shot example selectors can be used out-of-the box to achieve this same goal. LangSmith will index the dataset for you and enable retrieval of few shot examples that are most relevant to the user input based upon keyword similarity ([using a BM25-like algorithm](https://docs.smith.langchain.com/how_to_guides/datasets/index_datasets_for_dynamic_few_shot_example_selection) for keyword based similarity). 

See this how-to [video](https://www.youtube.com/watch?v=37VaU7e7t5o) for example usage of dynamic few-shot example selection in LangSmith. Also, see this [blog post](https://blog.langchain.dev/few-shot-prompting-to-improve-tool-calling-performance/) showcasing few-shot prompting to improve tool calling performance and this [blog post](https://blog.langchain.dev/aligning-llm-as-a-judge-with-human-preferences/) using few-shot example to align an LLMs to human preferences.




#### Procedural memory

[Procedural memory](https://en.wikipedia.org/wiki/Procedural_memory), in both humans and AI agents, involves remembering the rules used to perform tasks. In humans, procedural memory is like the internalized knowledge of how to perform tasks, such as riding a bike via basic motor skills and balance. Episodic memory, on the other hand, involves recalling specific experiences, such as the first time you successfully rode a bike without training wheels or a memorable bike ride through a scenic route. For AI agents, procedural memory is a combination of model weights, agent code, and agent's prompt that collectively determine the agent's functionality. 

In practice, it is fairly uncommon for agents to modify their model weights or rewrite their code. However, it is more common for agents to modify their own prompts. 

One effective approach to refining an agent's instructions is through ["Reflection"](https://blog.langchain.dev/reflection-agents/) or meta-prompting. This involves prompting the agent with its current instructions (e.g., the system prompt) along with recent conversations or explicit user feedback. The agent then refines its own instructions based on this input. This method is particularly useful for tasks where instructions are challenging to specify upfront, as it allows the agent to learn and adapt from its interactions.

For example, we built a [Tweet generator](https://www.youtube.com/watch?v=Vn8A3BxfplE) using external feedback and prompt re-writing to produce high-quality paper summaries for Twitter. In this case, the specific summarization prompt was difficult to specify *a priori*, but it was fairly easy for a user to critique the generated Tweets and provide feedback on how to improve the summarization process. 

The below pseudo-code shows how you might implement this with the LangGraph memory [store](persistence.md#memory-store), using the store to save a prompt, the `update_instructions` node to get the current prompt (as well as feedback from the conversation with the user captured in `state["messages"]`), update the prompt, and save the new prompt back to the store. Then, the `call_model` get the updated prompt from the store and uses it to generate a response.

```python
# Node that *uses* the instructions
def call_model(state: State, store: BaseStore):
    namespace = ("agent_instructions", )
    instructions = store.get(namespace, key="agent_a")[0]
    # Application logic
    prompt = prompt_template.format(instructions=instructions.value["instructions"])
    ...

# Node that updates instructions
def update_instructions(state: State, store: BaseStore):
    namespace = ("instructions",)
    current_instructions = store.search(namespace)[0]
    # Memory logic
    prompt = prompt_template.format(instructions=instructions.value["instructions"], conversation=state["messages"])
    output = llm.invoke(prompt)
    new_instructions = output['new_instructions']
    store.put(("agent_instructions",), "agent_a", {"instructions": new_instructions})
    ...
```




![](img/memory/update-instructions.png)

### Writing memories

There are two primary methods for agents to write memories: ["in the hot path"](#in-the-hot-path) and ["in the background"](#in-the-background).

![](img/memory/hot_path_vs_background.png)

#### In the hot path

Creating memories during runtime offers both advantages and challenges. On the positive side, this approach allows for real-time updates, making new memories immediately available for use in subsequent interactions. It also enables transparency, as users can be notified when memories are created and stored.

However, this method also presents challenges. It may increase complexity if the agent requires a new tool to decide what to commit to memory. In addition, the process of reasoning about what to save to memory can impact agent latency. Finally, the agent must multitask between memory creation and its other responsibilities, potentially affecting the quantity and quality of memories created.

As an example, ChatGPT uses a [save_memories](https://openai.com/index/memory-and-new-controls-for-chatgpt/) tool to upsert memories as content strings, deciding whether and how to use this tool with each user message. See our [memory-agent](https://github.com/langchain-ai/memory-agent) template as an reference implementation.

#### In the background

Creating memories as a separate background task offers several advantages. It eliminates latency in the primary application, separates application logic from memory management, and allows for more focused task completion by the agent. This approach also provides flexibility in timing memory creation to avoid redundant work.

However, this method has its own challenges. Determining the frequency of memory writing becomes crucial, as infrequent updates may leave other threads without new context. Deciding when to trigger memory formation is also important. Common strategies include scheduling after a set time period (with rescheduling if new events occur), using a cron schedule, or allowing manual triggers by users or the application logic.

See our [memory-service](https://github.com/langchain-ai/memory-template) template as an reference implementation.

### Memory storage

LangGraph stores long-term memories as JSON documents in a [store](persistence.md#memory-store). Each memory is organized under a custom `namespace` (similar to a folder) and a distinct `key` (like a file name). Namespaces often include user or org IDs or other labels that makes it easier to organize information. This structure enables hierarchical organization of memories. Cross-namespace searching is then supported through content filters.

```python
from langgraph.store.memory import InMemoryStore


def embed(texts: list[str]) -> list[list[float]]:
    # Replace with an actual embedding function or LangChain embeddings object
    return [[1.0, 2.0] * len(texts)]


# InMemoryStore saves data to an in-memory dictionary. Use a DB-backed store in production use.
store = InMemoryStore(index={"embed": embed, "dims": 2})
user_id = "my-user"
application_context = "chitchat"
namespace = (user_id, application_context)
store.put(
    namespace,
    "a-memory",
    {
        "rules": [
            "User likes short, direct language",
            "User only speaks English & python",
        ],
        "my-key": "my-value",
    },
)
# get the "memory" by ID
item = store.get(namespace, "a-memory")
# search for "memories" within this namespace, filtering on content equivalence, sorted by vector similarity
items = store.search(
    namespace, filter={"my-key": "my-value"}, query="language preferences"
)
```




For more information about the memory store, see the [Persistence](persistence.md#memory-store) guide.

Source: https://langchain-ai.github.io/langgraph/agents/context/

# Context

**Context engineering** is the practice of building dynamic systems that provide the right information and tools, in the right format, so that an AI application can accomplish a task. Context can be characterized along two key dimensions:

1. By **mutability**:
    - **Static context**: Immutable data that doesn't change during execution (e.g., user metadata, database connections, tools)
    - **Dynamic context**: Mutable data that evolves as the application runs (e.g., conversation history, intermediate results, tool call observations)
2. By **lifetime**:
    - **Runtime context**: Data scoped to a single run or invocation
    - **Cross-conversation context**: Data that persists across multiple conversations or sessions

!!! tip "Runtime context vs LLM context"

    Runtime context refers to local context: data and dependencies your code needs to run. It does **not** refer to:

    * The LLM context, which is the data passed into the LLM's prompt.
    * The "context window", which is the maximum number of tokens that can be passed to the LLM.

    Runtime context can be used to optimize the LLM context. For example, you can use user metadata
    in the runtime context to fetch user preferences and feed them into the context window.

LangGraph provides three ways to manage context, which combines the mutability and lifetime dimensions:

| Context type                                                                                | Description                                            | Mutability | Lifetime           | Access method                           |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ---------- | ------------------ | --------------------------------------- |
| [**Static runtime context**](#static-runtime-context)                                       | User metadata, tools, db connections passed at startup | Static     | Single run         | `context` argument to `invoke`/`stream` |
| [**Dynamic runtime context (state)**](#dynamic-runtime-context-state)                       | Mutable data that evolves during a single run          | Dynamic    | Single run         | LangGraph state object                  |
| [**Dynamic cross-conversation context (store)**](#dynamic-cross-conversation-context-store) | Persistent data shared across conversations            | Dynamic    | Cross-conversation | LangGraph store                         |

## Static runtime context

**Static runtime context** represents immutable data like user metadata, tools, and database connections that are passed to an application at the start of a run via the `context` argument to `invoke`/`stream`. This data does not change during execution.

!!! version-added "New in LangGraph v0.6: `context` replaces `config['configurable']`"

    Runtime context is now passed to the `context` argument of `invoke`/`stream`,
    which replaces the previous pattern of passing application configuration to `config['configurable']`.

```python hl_lines="7"
@dataclass
class ContextSchema:
    user_name: str

graph.invoke( # (1)!
    {"messages": [{"role": "user", "content": "hi!"}]}, # (2)!
    context={"user_name": "John Smith"} # (3)!
)
```

1. This is the invocation of the agent or graph. The `invoke` method runs the underlying graph with the provided input.
2. This example uses messages as an input, which is common, but your application may use different input structures.
3. This is where you pass the runtime data. The `context` parameter allows you to provide additional dependencies that the agent can use during its execution.

=== "Agent prompt"

    ```python hl_lines="6 20"
    from langchain_core.messages import AnyMessage
    from langgraph.runtime import get_runtime
    from langgraph.prebuilt.chat_agent_executor import AgentState
    from langgraph.prebuilt import create_react_agent

    def prompt(state: AgentState) -> list[AnyMessage]:
        runtime = get_runtime(ContextSchema)
        system_msg = f"You are a helpful assistant. Address the user as {runtime.context.user_name}."
        return [{"role": "system", "content": system_msg}] + state["messages"]

    agent = create_react_agent(
        model="anthropic:claude-3-7-sonnet-latest",
        tools=[get_weather],
        prompt=prompt,
        context_schema=ContextSchema
    )

    agent.invoke(
        {"messages": [{"role": "user", "content": "what is the weather in sf"}]},
        context={"user_name": "John Smith"}
    )
    ```

    * See [Agents](../agents/agents.md) for details.

=== "Workflow node"

    ```python hl_lines="3"
    from langgraph.runtime import Runtime

    def node(state: State, config: Runtime[ContextSchema]):
        user_name = runtime.context.user_name
        ...
    ```

    * See [the Graph API](https://langchain-ai.github.io/langgraph/how-tos/graph-api/#add-runtime-configuration) for details.

=== "In a tool"

    ```python hl_lines="4"
    from langgraph.runtime import get_runtime

    @tool
    def get_user_email() -> str:
        """Retrieve user information based on user ID."""
        # simulate fetching user info from a database
        runtime = get_runtime(ContextSchema)
        email = get_user_email_from_db(runtime.context.user_name)
        return email
    ```

    See the [tool calling guide](../how-tos/tool-calling.md#configuration) for details.

!!! tip

    The `Runtime` object can be used to access static context and other utilities like the active store and stream writer.
    See the [Runtime][langgraph.runtime.Runtime] documentation for details.





## Dynamic runtime context (state)

**Dynamic runtime context** represents mutable data that can evolve during a single run and is managed through the LangGraph state object. This includes conversation history, intermediate results, and values derived from tools or LLM outputs. In LangGraph, the state object acts as [short-term memory](../concepts/memory.md) during a run.

=== "In an agent"

    Example shows how to incorporate state into an agent **prompt**.

    State can also be accessed by the agent's **tools**, which can read or update the state as needed. See [tool calling guide](../how-tos/tool-calling.md#short-term-memory) for details.

    ```python hl_lines="6 10 19"
    from langchain_core.messages import AnyMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.prebuilt import create_react_agent
    from langgraph.prebuilt.chat_agent_executor import AgentState

    class CustomState(AgentState): # (1)!
        user_name: str

    def prompt(
        state: CustomState
    ) -> list[AnyMessage]:
        user_name = state["user_name"]
        system_msg = f"You are a helpful assistant. User's name is {user_name}"
        return [{"role": "system", "content": system_msg}] + state["messages"]

    agent = create_react_agent(
        model="anthropic:claude-3-7-sonnet-latest",
        tools=[...],
        state_schema=CustomState, # (2)!
        prompt=prompt
    )

    agent.invoke({
        "messages": "hi!",
        "user_name": "John Smith"
    })
    ```

    1. Define a custom state schema that extends `AgentState` or `MessagesState`.
    2. Pass the custom state schema to the agent. This allows the agent to access and modify the state during execution.




=== "In a workflow"

    ```python hl_lines="5 9 13"
    from typing_extensions import TypedDict
    from langchain_core.messages import AnyMessage
    from langgraph.graph import StateGraph

    class CustomState(TypedDict): # (1)!
        messages: list[AnyMessage]
        extra_field: int

    def node(state: CustomState): # (2)!
        messages = state["messages"]
        ...
        return { # (3)!
            "extra_field": state["extra_field"] + 1
        }

    builder = StateGraph(State)
    builder.add_node(node)
    builder.set_entry_point("node")
    graph = builder.compile()
    ```

    1. Define a custom state
    2. Access the state in any node or tool
    3. The Graph API is designed to work as easily as possible with state. The return value of a node represents a requested update to the state.




!!! tip "Turning on memory"

    Please see the [memory guide](../how-tos/memory/add-memory.md) for more details on how to enable memory. This is a powerful feature that allows you to persist the agent's state across multiple invocations. Otherwise, the state is scoped only to a single run.

## Dynamic cross-conversation context (store)

**Dynamic cross-conversation context** represents persistent, mutable data that spans across multiple conversations or sessions and is managed through the LangGraph store. This includes user profiles, preferences, and historical interactions. The LangGraph store acts as [long-term memory](../concepts/memory.md#long-term-memory) across multiple runs. This can be used to read or update persistent facts (e.g., user profiles, preferences, prior interactions).

For more information, see the [Memory guide](../how-tos/memory/add-memory.md).

Source: https://langchain-ai.github.io/langgraph/agents/models/

# Models

LangGraph provides built-in support for [LLMs (language models)](https://python.langchain.com/docs/concepts/chat_models/) via the LangChain library. This makes it easy to integrate various LLMs into your agents and workflows.

## Initialize a model

Use [`init_chat_model`](https://python.langchain.com/docs/how_to/chat_models_universal_init/) to initialize models:

=== "OpenAI"

    ```shell
    pip install -U "langchain[openai]"
    ```
    ```python
    import os
    from langchain.chat_models import init_chat_model

    os.environ["OPENAI_API_KEY"] = "sk-..."

    llm = init_chat_model("openai:gpt-4.1")
    ```

    👉 Read the [OpenAI integration docs](https://python.langchain.com/docs/integrations/chat/openai/)

=== "Anthropic"

    ```shell
    pip install -U "langchain[anthropic]"
    ```
    ```python
    import os
    from langchain.chat_models import init_chat_model

    os.environ["ANTHROPIC_API_KEY"] = "sk-..."

    llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")
    ```

    👉 Read the [Anthropic integration docs](https://python.langchain.com/docs/integrations/chat/anthropic/)

=== "Azure"

    ```shell
    pip install -U "langchain[openai]"
    ```
    ```python
    import os
    from langchain.chat_models import init_chat_model

    os.environ["AZURE_OPENAI_API_KEY"] = "..."
    os.environ["AZURE_OPENAI_ENDPOINT"] = "..."
    os.environ["OPENAI_API_VERSION"] = "2025-03-01-preview"

    llm = init_chat_model(
        "azure_openai:gpt-4.1",
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
    )
    ```
 
    👉 Read the [Azure integration docs](https://python.langchain.com/docs/integrations/chat/azure_chat_openai/)

=== "Google Gemini"

    ```shell
    pip install -U "langchain[google-genai]"
    ```
    ```python
    import os
    from langchain.chat_models import init_chat_model

    os.environ["GOOGLE_API_KEY"] = "..."

    llm = init_chat_model("google_genai:gemini-2.0-flash")
    ```

    👉 Read the [Google GenAI integration docs](https://python.langchain.com/docs/integrations/chat/google_generative_ai/)

=== "AWS Bedrock"

    ```shell
    pip install -U "langchain[aws]"
    ```
    ```python
    from langchain.chat_models import init_chat_model

    # Follow the steps here to configure your credentials:
    # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html

    llm = init_chat_model(
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        model_provider="bedrock_converse",
    )
    ```

    👉 Read the [AWS Bedrock integration docs](https://python.langchain.com/docs/integrations/chat/bedrock/)





### Instantiate a model directly

If a model provider is not available via `init_chat_model`, you can instantiate the provider's model class directly. The model must implement the [BaseChatModel interface](https://python.langchain.com/api_reference/core/language_models/langchain_core.language_models.chat_models.BaseChatModel.html) and support tool calling:

API Reference: ChatAnthropic</a></i></sup>

```python
# Anthropic is already supported by `init_chat_model`,
# but you can also instantiate it directly.
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(
  model="claude-3-7-sonnet-latest",
  temperature=0,
  max_tokens=2048
)
```



!!! important "Tool calling support"

    If you are building an agent or workflow that requires the model to call external tools, ensure that the underlying
    language model supports [tool calling](../concepts/tools.md). Compatible models can be found in the [LangChain integrations directory](https://python.langchain.com/docs/integrations/chat/).

## Use in an agent

When using `create_react_agent` you can specify the model by its name string, which is a shorthand for initializing the model using `init_chat_model`. This allows you to use the model without needing to import or instantiate it directly.

=== "model name"

      ```python hl_lines="4"
      from langgraph.prebuilt import create_react_agent

      create_react_agent(
         model="anthropic:claude-3-7-sonnet-latest",
         # other parameters
      )
      ```

=== "model instance"

      ```python hl_lines="13"
      from langchain_anthropic import ChatAnthropic
      from langgraph.prebuilt import create_react_agent

      model = ChatAnthropic(
          model="claude-3-7-sonnet-latest",
          temperature=0,
          max_tokens=2048
      )
      # Alternatively
      # model = init_chat_model("anthropic:claude-3-7-sonnet-latest")

      agent = create_react_agent(
        model=model,
        # other parameters
      )
      ```





### Dynamic model selection

Pass a callable function to `create_react_agent` to dynamically select the model at runtime. This is useful for scenarios where you want to choose a model based on user input, configuration settings, or other runtime conditions.

The selector function must return a chat model. If you're using tools, you must bind the tools to the model within the selector function.

  API Reference: init_chat_model</a> | BaseChatModel</a> | tool</a> | create_react_agent</a> | AgentState</a></i></sup>

```python
from dataclasses import dataclass
from typing import Literal
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.runtime import Runtime

@tool
def weather() -> str:
    """Returns the current weather conditions."""
    return "It's nice and sunny."


# Define the runtime context
@dataclass
class CustomContext:
    provider: Literal["anthropic", "openai"]

# Initialize models
openai_model = init_chat_model("openai:gpt-4o")
anthropic_model = init_chat_model("anthropic:claude-sonnet-4-20250514")


# Selector function for model choice
def select_model(state: AgentState, runtime: Runtime[CustomContext]) -> BaseChatModel:
    if runtime.context.provider == "anthropic":
        model = anthropic_model
    elif runtime.context.provider == "openai":
        model = openai_model
    else:
        raise ValueError(f"Unsupported provider: {runtime.context.provider}")

    # With dynamic model selection, you must bind tools explicitly
    return model.bind_tools([weather])


# Create agent with dynamic model selection
agent = create_react_agent(select_model, tools=[weather])

# Invoke with context to select model
output = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Which model is handling this?",
            }
        ]
    },
    context=CustomContext(provider="openai"),
)

print(output["messages"][-1].text())
```

!!! version-added "New in LangGraph v0.6"



## Advanced model configuration

### Disable streaming

To disable streaming of the individual LLM tokens, set `disable_streaming=True` when initializing the model:

=== "`init_chat_model`"

    ```python hl_lines="5"
    from langchain.chat_models import init_chat_model

    model = init_chat_model(
        "anthropic:claude-3-7-sonnet-latest",
        disable_streaming=True
    )
    ```

=== "`ChatModel`"

    ```python hl_lines="5"
    from langchain_anthropic import ChatAnthropic

    model = ChatAnthropic(
        model="claude-3-7-sonnet-latest",
        disable_streaming=True
    )
    ```

Refer to the [API reference](https://python.langchain.com/api_reference/core/language_models/langchain_core.language_models.chat_models.BaseChatModel.html#langchain_core.language_models.chat_models.BaseChatModel.disable_streaming) for more information on `disable_streaming`




### Add model fallbacks

You can add a fallback to a different model or a different LLM provider using `model.with_fallbacks([...])`:

=== "`init_chat_model`"

    ```python hl_lines="5"
    from langchain.chat_models import init_chat_model

    model_with_fallbacks = (
        init_chat_model("anthropic:claude-3-5-haiku-latest")
        .with_fallbacks([
            init_chat_model("openai:gpt-4.1-mini"),
        ])
    )
    ```

=== "`ChatModel`"

    ```python hl_lines="6"
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    model_with_fallbacks = (
        ChatAnthropic(model="claude-3-5-haiku-latest")
        .with_fallbacks([
            ChatOpenAI(model="gpt-4.1-mini"),
        ])
    )
    ```

See this [guide](https://python.langchain.com/docs/how_to/fallbacks/#fallback-to-better-model) for more information on model fallbacks.




### Use the built-in rate limiter

Langchain includes a built-in in-memory rate limiter. This rate limiter is thread safe and can be shared by multiple threads in the same process.

API Reference: InMemoryRateLimiter</a> | ChatAnthropic</a></i></sup>

```python
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_anthropic import ChatAnthropic

rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.1,  # <-- Super slow! We can only make a request once every 10 seconds!!
    check_every_n_seconds=0.1,  # Wake up every 100 ms to check whether allowed to make a request,
    max_bucket_size=10,  # Controls the maximum burst size.
)

model = ChatAnthropic(
   model_name="claude-3-opus-20240229",
   rate_limiter=rate_limiter
)
```

See the LangChain docs for more information on how to [handle rate limiting](https://python.langchain.com/docs/how_to/chat_model_rate_limiting/).


## Bring your own model

If your desired LLM isn't officially supported by LangChain, consider these options:

1. **Implement a custom LangChain chat model**: Create a model conforming to the [LangChain chat model interface](https://python.langchain.com/docs/how_to/custom_chat_model/). This enables full compatibility with LangGraph's agents and workflows but requires understanding of the LangChain framework.




2. **Direct invocation with custom streaming**: Use your model directly by [adding custom streaming logic](../how-tos/streaming.md#use-with-any-llm) with `StreamWriter`.
   Refer to the [custom streaming documentation](../how-tos/streaming.md#use-with-any-llm) for guidance. This approach suits custom workflows where prebuilt agent integration is not necessary.

## Additional resources

- [Multimodal inputs](https://python.langchain.com/docs/how_to/multimodal_inputs/)
- [Structured outputs](https://python.langchain.com/docs/how_to/structured_output/)
- [Model integration directory](https://python.langchain.com/docs/integrations/chat/)
- [Force model to call a specific tool](https://python.langchain.com/docs/how_to/tool_choice/)
- [All chat model how-to guides](https://python.langchain.com/docs/how_to/#chat-models)
- [Chat model integrations](https://python.langchain.com/docs/integrations/chat/)



Source: https://langchain-ai.github.io/langgraph/concepts/tools/

# Tools

Many AI applications interact with users via natural language. However, some use cases require models to interface directly with external systems—such as APIs, databases, or file systems—using structured input. In these scenarios, [tool calling](../how-tos/tool-calling.md) enables models to generate requests that conform to a specified input schema.

**Tools** encapsulate a callable function and its input schema. These can be passed to compatible [chat models](https://python.langchain.com/docs/concepts/chat_models), allowing the model to decide whether to invoke a tool and with what arguments.




## Tool calling

![Diagram of a tool call by a model](./img/tool_call.png)

Tool calling is typically **conditional**. Based on the user input and available tools, the model may choose to issue a tool call request. This request is returned in an `AIMessage` object, which includes a `tool_calls` field that specifies the tool name and input arguments:

```python
llm_with_tools.invoke("What is 2 multiplied by 3?")
# -> AIMessage(tool_calls=[{'name': 'multiply', 'args': {'a': 2, 'b': 3}, ...}])
```

```
AIMessage(
  tool_calls=[
    ToolCall(name="multiply", args={"a": 2, "b": 3}),
    ...
  ]
)
```





If the input is unrelated to any tool, the model returns only a natural language message:

```python
llm_with_tools.invoke("Hello world!")  # -> AIMessage(content="Hello!")
```





Importantly, the model does not execute the tool—it only generates a request. A separate executor (such as a runtime or agent) is responsible for handling the tool call and returning the result.

See the [tool calling guide](../how-tos/tool-calling.md) for more details.

## Prebuilt tools

LangChain provides prebuilt tool integrations for common external systems including APIs, databases, file systems, and web data.

Browse the [integrations directory](https://python.langchain.com/docs/integrations/tools/) for available tools.




Common categories:

- **Search**: Bing, SerpAPI, Tavily
- **Code execution**: Python REPL, Node.js REPL
- **Databases**: SQL, MongoDB, Redis
- **Web data**: Scraping and browsing
- **APIs**: OpenWeatherMap, NewsAPI, etc.

## Custom tools

You can define custom tools using the `@tool` decorator or plain Python functions. For example:

API Reference: tool</a></i></sup>

```python
from langchain_core.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
```





See the [tool calling guide](../how-tos/tool-calling.md) for more details.

## Tool execution

While the model determines when to call a tool, execution of the tool call must be handled by a runtime component.

LangGraph provides prebuilt components for this:

- [`ToolNode`](https://langchain-ai.github.io/langgraph/reference/agents/#langgraph.prebuilt.tool_node.ToolNode): A prebuilt node that executes tools.
- [`create_react_agent`](https://langchain-ai.github.io/langgraph/reference/prebuilt/#langgraph.prebuilt.chat_agent_executor.create_react_agent): Constructs a full agent that manages tool calling automatically.



Source: https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/

# Human-in-the-loop

To review, edit, and approve tool calls in an agent or workflow, [use LangGraph's human-in-the-loop features](../how-tos/human_in_the_loop/add-human-in-the-loop.md) to enable human intervention at any point in a workflow. This is especially useful in large language model (LLM)-driven applications where model output may require validation, correction, or additional context.


![image](../concepts/img/human_in_the_loop/tool-call-review.png){: style="max-height:400px"}
</figure>

!!! tip

    For information on how to use human-in-the-loop, see [Enable human intervention](../how-tos/human_in_the_loop/add-human-in-the-loop.md) and [Human-in-the-loop using Server API](../cloud/how-tos/add-human-in-the-loop.md).

## Key capabilities

* **Persistent execution state**: Interrupts use LangGraph's [persistence](./persistence.md) layer, which saves the graph state, to indefinitely pause graph execution until you resume. This is possible because LangGraph checkpoints the graph state after each step, which allows the system to persist execution context and later resume the workflow, continuing from where it left off. This supports asynchronous human review or input without time constraints.

    There are two ways to pause a graph:

    - [Dynamic interrupts](../how-tos/human_in_the_loop/add-human-in-the-loop.md#pause-using-interrupt): Use `interrupt` to pause a graph from inside a specific node, based on the current state of the graph.
    - [Static interrupts](../how-tos/human_in_the_loop/add-human-in-the-loop.md#debug-with-interrupts): Use `interrupt_before` and `interrupt_after` to pause the graph at pre-defined points, either before or after a node executes.

    
    ![image](./img/breakpoints.png){: style="max-height:400px"}
    An example graph consisting of 3 sequential steps with a breakpoint before step_3. </figcaption> </figure>

* **Flexible integration points**: Human-in-the-loop logic can be introduced at any point in the workflow. This allows targeted human involvement, such as approving API calls, correcting outputs, or guiding conversations.

## Patterns

There are four typical design patterns that you can implement using `interrupt` and `Command`:

- [Approve or reject](../how-tos/human_in_the_loop/add-human-in-the-loop.md#approve-or-reject): Pause the graph before a critical step, such as an API call, to review and approve the action. If the action is rejected, you can prevent the graph from executing the step, and potentially take an alternative action. This pattern often involves routing the graph based on the human's input.
- [Edit graph state](../how-tos/human_in_the_loop/add-human-in-the-loop.md#review-and-edit-state): Pause the graph to review and edit the graph state. This is useful for correcting mistakes or updating the state with additional information. This pattern often involves updating the state with the human's input.
- [Review tool calls](../how-tos/human_in_the_loop/add-human-in-the-loop.md#review-tool-calls): Pause the graph to review and edit tool calls requested by the LLM before tool execution.
- [Validate human input](../how-tos/human_in_the_loop/add-human-in-the-loop.md#validate-human-input): Pause the graph to validate human input before proceeding with the next step.Source: https://langchain-ai.github.io/langgraph/concepts/time-travel/

# Time Travel ⏱️

When working with non-deterministic systems that make model-based decisions (e.g., agents powered by LLMs), it can be useful to examine their decision-making process in detail:

1. 🤔 **Understand reasoning**: Analyze the steps that led to a successful result.
2. 🐞 **Debug mistakes**: Identify where and why errors occurred.
3. 🔍 **Explore alternatives**: Test different paths to uncover better solutions.

LangGraph provides [time travel functionality](../how-tos/human_in_the_loop/time-travel.md) to support these use cases. Specifically, you can resume execution from a prior checkpoint — either replaying the same state or modifying it to explore alternatives. In all cases, resuming past execution produces a new fork in the history.

!!! tip

    For information on how to use time travel, see [Use time travel](../how-tos/human_in_the_loop/time-travel.md) and [Time travel using Server API](../cloud/how-tos/human_in_the_loop_time_travel.md).
Source: https://langchain-ai.github.io/langgraph/concepts/subgraphs/

# Subgraphs

A subgraph is a [graph](./low_level.md#graphs) that is used as a [node](./low_level.md#nodes) in another graph — this is the concept of encapsulation applied to LangGraph. Subgraphs allow you to build complex systems with multiple components that are themselves graphs.

![Subgraph](./img/subgraph.png)

Some reasons for using subgraphs are:

- building [multi-agent systems](./multi_agent.md)
- when you want to reuse a set of nodes in multiple graphs
- when you want different teams to work on different parts of the graph independently, you can define each part as a subgraph, and as long as the subgraph interface (the input and output schemas) is respected, the parent graph can be built without knowing any details of the subgraph

The main question when adding subgraphs is how the parent graph and subgraph communicate, i.e. how they pass the [state](./low_level.md#state) between each other during the graph execution. There are two scenarios:

- parent and subgraph have **shared state keys** in their state [schemas](./low_level.md#state). In this case, you can [include the subgraph as a node in the parent graph](../how-tos/subgraph.ipynb#shared-state-schemas)

  ```python hl_lines="12 17"
  from langgraph.graph import StateGraph, MessagesState, START

  # Subgraph

  def call_model(state: MessagesState):
      response = model.invoke(state["messages"])
      return {"messages": response}

  subgraph_builder = StateGraph(State)
  subgraph_builder.add_node(call_model)
  ...
  subgraph = subgraph_builder.compile()

  # Parent graph

  builder = StateGraph(State)
  builder.add_node("subgraph_node", subgraph)
  builder.add_edge(START, "subgraph_node")
  graph = builder.compile()
  ...
  graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
  ```





- parent graph and subgraph have **different schemas** (no shared state keys in their state [schemas](./low_level.md#state)). In this case, you have to [call the subgraph from inside a node in the parent graph](../how-tos/subgraph.ipynb#different-state-schemas): this is useful when the parent graph and the subgraph have different state schemas and you need to transform state before or after calling the subgraph

  ```python hl_lines="7 11 19 28"
  from typing_extensions import TypedDict, Annotated
  from langchain_core.messages import AnyMessage
  from langgraph.graph import StateGraph, MessagesState, START
  from langgraph.graph.message import add_messages

  class SubgraphMessagesState(TypedDict):
      subgraph_messages: Annotated[list[AnyMessage], add_messages]

  # Subgraph

  def call_model(state: SubgraphMessagesState):
      response = model.invoke(state["subgraph_messages"])
      return {"subgraph_messages": response}

  subgraph_builder = StateGraph(SubgraphMessagesState)
  subgraph_builder.add_node("call_model_from_subgraph", call_model)
  subgraph_builder.add_edge(START, "call_model_from_subgraph")
  ...
  subgraph = subgraph_builder.compile()

  # Parent graph

  def call_subgraph(state: MessagesState):
      response = subgraph.invoke({"subgraph_messages": state["messages"]})
      return {"messages": response["subgraph_messages"]}

  builder = StateGraph(State)
  builder.add_node("subgraph_node", call_subgraph)
  builder.add_edge(START, "subgraph_node")
  graph = builder.compile()
  ...
  graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
  ```




Source: https://langchain-ai.github.io/langgraph/concepts/mcp/

# MCP

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) is an open protocol that standardizes how applications provide tools and context to language models. LangGraph agents can use tools defined on MCP servers through the `langchain-mcp-adapters` library.

![MCP](../agents/assets/mcp.png)

Install the `langchain-mcp-adapters` library to use MCP tools in LangGraph:

```bash
pip install langchain-mcp-adapters
```



