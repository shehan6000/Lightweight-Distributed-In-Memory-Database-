# 🗄️ Lightweight Distributed In-Memory Database

A minimal, educational implementation of a distributed in-memory database designed to run entirely within Google Colab notebooks. This project demonstrates core distributed systems concepts in Python without external dependencies.

## 📚 Table of Contents
- [Overview](#overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Core Concepts Explained](#-core-concepts-explained)
- [API Reference](#-api-reference)
- [Learning Journey](#-learning-journey)
- [Use Cases](#-use-cases)
- [Limitations](#-limitations)
- [Contributing](#-contributing)
- [License](#-license)

## Overview

This project implements a lightweight distributed database system that demonstrates fundamental distributed computing concepts. It's specifically designed for **educational purposes** to help learners understand how distributed databases work under the hood.

### Why This Project?
- **Learn by Doing**: Understand distributed systems through implementation
- **Colab-First**: Runs entirely in Google Colab notebooks
- **Zero Dependencies**: Pure Python implementation
- **Modular Design**: Each component is separated for easy understanding

## 🚀 Features

### Core Database Features
- ✅ **Distributed CRUD Operations** (Create, Read, Update, Delete)
- ✅ **Consistent Hashing** for data distribution
- ✅ **Configurable Replication** (ONE, QUORUM, ALL)
- ✅ **Write-Ahead Logging (WAL)** for durability
- ✅ **Basic SQL-like Query Interface**

### Distribution Features
- ✅ **Automatic Sharding** across nodes
- ✅ **Fault Tolerance** through replication
- ✅ **Dynamic Node Membership** (join/leave)
- ✅ **Load Balancing** via virtual nodes
- ✅ **Conflict Resolution** strategies

### Educational Features
- ✅ **Commented Source Code** with explanations
- ✅ **Step-by-Step Demos**
- ✅ **Visual Status Displays**
- ✅ **Performance Metrics**
- ✅ **Simulated Network Effects**

## 🏗️ Architecture

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Client Interface                      │
│  (DistributedDBClient / ColabDistributedDB)             │
└───────────────────────┬─────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         │    Consistent Hash Ring      │
         │  (Determines data placement) │
         └──────────────┬──────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
┌───▼────┐         ┌───▼────┐         ┌───▼────┐
│ Node 1 │         │ Node 2 │         │ Node 3 │
│ 8080   │         │ 8081   │         │ 8082   │
└───┬────┘         └───┬────┘         └───┬────┘
    │                  │                  │
┌───▼────┐       ┌────▼────┐       ┌────▼────┐
│ Data   │       │  Data   │       │  Data   │
│ Shard A│       │ Shard B │       │ Shard C │
│ Replica│       │ Replica │       │ Replica │
└────────┘       └─────────┘       └─────────┘
```

### Data Flow
1. **Client Request** → Hash Ring determines target node
2. **Primary Node** → Processes operation locally
3. **Replication** → Propagates to replica nodes (if configured)
4. **Quorum Check** → Verifies sufficient replicas responded
5. **Response** → Returns to client

### Key Components
1. **`DistributedDBNode`**: Individual database node with local storage
2. **`ConsistentHashRing`**: Distributes keys across nodes
3. **`DistributedDBClient`**: Client interface for applications
4. **`ColabDistributedDB`**: Simplified wrapper for Colab notebooks
5. **`WriteAheadLog`**: Durability mechanism for crash recovery

## 🎯 Quick Start

### Option 1: Single Notebook Demo (Recommended for Beginners)
```python
# Run in a single Colab cell
from distributed_db import ColabDistributedDB

# Create a 3-node cluster simulation
db = ColabDistributedDB(num_nodes=3)

# Create a table
db.create_table("students", {
    "id": "int",
    "name": "str",
    "grade": "str",
    "age": "int"
})

# Insert data
db.put("students", "s001", {"id": 1, "name": "Alice", "grade": "A", "age": 20})

# Retrieve data
student = db.get("students", "s001")
print(f"Retrieved: {student}")

# Query data
results = db.query("students", {"grade": "A"})
print(f"Students with grade A: {len(results)}")

# Check cluster status
db.status()
```

### Option 2: Full Distributed Simulation
```python
# Run the complete educational demo
from distributed_db import run_distributed_demo

# This runs a comprehensive demonstration
client, nodes = run_distributed_demo()
```

### Option 3: Manual Cluster Setup
```python
# Advanced: Manual control of individual nodes
from distributed_db import DistributedDBNode, DistributedDBClient

# Create bootstrap node
node1 = DistributedDBNode(node_id="leader", port=8080)
node1.join_cluster([])  # Start new cluster

# Create additional nodes
node2 = DistributedDBNode(node_id="follower1", port=8081)
node2.join_cluster(["127.0.0.1:8080"])

# Create client
client = DistributedDBClient(["127.0.0.1:8080"])

# Use the database
client.create_table("logs", {"timestamp": "float", "message": "str"})
client.put("logs", "log1", {"timestamp": 123456789, "message": "System started"})
```

## 📖 Core Concepts Explained

### 1. Consistent Hashing
```python
# How data is distributed across nodes
hash_ring = ConsistentHashRing(["node1:8080", "node2:8080", "node3:8080"])

# Each key maps to a specific node
key = "users:alice"
node = hash_ring.get_node(key)  # Returns "node2:8080" (for example)

# Virtual nodes ensure better distribution
# "node1" becomes ["node1:v0", "node1:v1", "node1:v2"] on the ring
```

**Why it matters**: Prevents massive data movement when nodes join/leave.

### 2. Replication Strategies
```python
# Different consistency levels
client.put("table", "key", "value", replication='one')     # Fast, less reliable
client.put("table", "key", "value", replication='quorum')  # Balanced (default)
client.put("table", "key", "value", replication='all')     # Slow, most reliable

# Quorum calculation
replication_factor = 3
write_quorum = (replication_factor // 2) + 1  # = 2
read_quorum = (replication_factor // 2) + 1   # = 2
```

**Learning Point**: Trade-off between consistency and availability.

### 3. Write-Ahead Logging (WAL)
```python
# Every write operation creates a WAL entry
wal_entry = {
    "operation": "SET",
    "key": "users:alice",
    "value": {"name": "Alice", "age": 25},
    "timestamp": 123456789.0,
    "sequence": 42
}

# On crash recovery:
# 1. Read WAL from disk
# 2. Replay operations in sequence order
# 3. Restore database state
```

**Purpose**: Ensures durability even if system crashes.

### 4. Partitioning (Sharding)
```python
# Data is partitioned by key ranges
partitions = {
    0: (0, 1000),          # Node 1 handles keys 0-1000
    1: (1001, 2000),       # Node 2 handles keys 1001-2000
    2: (2001, 3000)        # Node 3 handles keys 2001-3000
}

# Hash function determines partition
key_hash = hash("users:alice") % 3000  # Returns 1423 → Partition 1
```

**Benefit**: Parallel processing and horizontal scaling.

## 📚 API Reference

### `ColabDistributedDB` (Simplified Interface)
```python
db = ColabDistributedDB(num_nodes=3)

# Core Operations
db.put(table, key, value, replication='quorum')
db.get(table, key, consistency='quorum')
db.delete(table, key, replication='quorum')
db.query(table, conditions=None)

# Schema Management
db.create_table(table, schema)

# Monitoring
db.status()
db.demo()  # Run interactive demo
```

### `DistributedDBClient` (Advanced Interface)
```python
client = DistributedDBClient(bootstrap_nodes=["127.0.0.1:8080"])

# Same operations as ColabDistributedDB plus:
client.print_cluster_info()  # Detailed cluster status
```

### `DistributedDBNode` (Node-Level Control)
```python
node = DistributedDBNode(node_id="node1", port=8080)

# Cluster management
node.join_cluster(bootstrap_nodes)
node.leave_cluster()
node.get_cluster_state()

# Direct operations (bypassing client)
node.put(table, key, value, replication)
node.get(table, key, consistency)

# Monitoring
node.get_stats()
node.print_status()
```

## 🎓 Learning Journey

### Week 1: Understanding Basics
1. **Day 1**: Run the quick demo, understand basic operations
2. **Day 2**: Study the architecture diagram
3. **Day 3**: Implement a simple key-value store (single node)
4. **Day 4**: Add persistence with Write-Ahead Logging
5. **Day 5**: Create unit tests for basic operations

### Week 2: Distribution Concepts
1. **Day 6**: Implement consistent hashing
2. **Day 7**: Add node discovery and cluster formation
3. **Day 8**: Implement data replication
4. **Day 9**: Add quorum-based operations
5. **Day 10**: Test fault tolerance (simulate node failures)

### Week 3: Advanced Features
1. **Day 11**: Implement conflict resolution
2. **Day 12**: Add basic query language
3. **Day 13**: Implement load balancing
4. **Day 14**: Add monitoring and metrics
5. **Day 15**: Performance optimization

### Week 4: Real-World Application
1. **Day 16**: Build a sample application (e.g., todo list)
2. **Day 17**: Benchmark performance
3. **Day 18**: Compare with other databases
4. **Day 19**: Document your learnings
5. **Day 20**: Present your project

## 🔧 Use Cases

### Educational Projects
- **Distributed Systems Course**: Practical implementation of theoretical concepts
- **Database Internals**: Understanding how databases work internally
- **Python Networking**: Learning about sockets, RPC, and inter-process communication

### Prototyping & Experimentation
- **Algorithm Testing**: Experiment with different hashing algorithms
- **Consistency Models**: Compare different consistency guarantees
- **Load Balancing Strategies**: Test various distribution approaches

### Small-Scale Applications
- **Session Storage**: Distributed session management for web apps
- **Configuration Management**: Distributed configuration storage
- **Real-time Analytics**: Simple distributed counters and aggregations

## ⚠️ Limitations & Production Notes

### What This Project IS:
- ✅ **Educational tool** for learning distributed systems
- ✅ **Prototyping platform** for algorithm experimentation
- ✅ **Reference implementation** of core concepts
- ✅ **Teaching aid** for database internals

### What This Project IS NOT:
- ❌ **Production-ready database** (missing many features)
- ❌ **High-performance system** (Python, single-threaded)
- ❌ **Fully persistent storage** (in-memory with basic WAL)
- ❌ **Security-hardened** (no authentication/encryption)

### Missing Production Features:
1. **Security**: No authentication, authorization, or encryption
2. **Persistence**: Limited durability mechanisms
3. **Transactions**: No ACID guarantees
4. **Advanced Queries**: No JOINs, complex aggregations
5. **Monitoring**: Basic metrics only
6. **Backup/Restore**: Limited backup capabilities

## 🧪 Experiments to Try

### Experiment 1: Performance Scaling
```python
# Measure how performance changes with node count
import time

for node_count in [1, 2, 3, 4, 5]:
    db = ColabDistributedDB(num_nodes=node_count)
    
    start = time.time()
    for i in range(100):
        db.put("test", f"key_{i}", {"value": i})
    
    duration = time.time() - start
    print(f"{node_count} nodes: {duration:.2f}s, {100/duration:.0f} ops/sec")
```

### Experiment 2: Fault Tolerance
```python
# Simulate node failure
db = ColabDistributedDB(num_nodes=3)

# Store data with replication
db.put("important", "key1", "value1", replication='quorum')

# Simulate 1 node failing (in real system, kill a node)
print("Simulating node failure...")
# Data should still be accessible!

retrieved = db.get("important", "key1")
print(f"After node failure, retrieved: {retrieved}")
```

### Experiment 3: Consistency Trade-offs
```python
# Compare different consistency levels
import time

db = ColabDistributedDB(num_nodes=3)

consistency_levels = ['one', 'quorum', 'all']
results = {}

for consistency in consistency_levels:
    start = time.time()
    
    # Write with this consistency
    for i in range(50):
        db.put("bench", f"key_{i}", {"data": i}, replication=consistency)
    
    # Read with same consistency
    for i in range(50):
        db.get("bench", f"key_{i}", consistency=consistency)
    
    duration = time.time() - start
    results[consistency] = duration
    print(f"{consistency}: {duration:.2f}s")

print("\nTrade-off: Speed vs. Reliability")
print(results)
```

## 🤝 Contributing

### Want to Improve This Project?
Here are some areas where you can contribute:

1. **Add Features**:
   - Implement secondary indexes
   - Add SQL parser for better queries
   - Implement two-phase commit for transactions
   - Add data compression

2. **Improve Performance**:
   - Implement connection pooling
   - Add async/await for better concurrency
   - Implement data serialization optimization

3. **Enhance Educational Value**:
   - Add more comments and explanations
   - Create visualizations of data distribution
   - Add interactive tutorials
   - Create comparison with real databases

### Contribution Guidelines:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Good First Issues:
- [ ] Add more comprehensive unit tests
- [ ] Implement LRU cache for frequently accessed data
- [ ] Add basic authentication mechanism
- [ ] Create Docker container for easy deployment
- [ ] Add data export to CSV/JSON

## 📖 Further Learning Resources

### Books
1. **"Designing Data-Intensive Applications"** by Martin Kleppmann
2. **"Database Internals"** by Alex Petrov
3. **"Distributed Systems: Principles and Paradigms"** by Andrew S. Tanenbaum

### Online Courses
1. **MIT 6.824: Distributed Systems** (YouTube)
2. **CMU 15-440: Distributed Systems** (Open Courseware)
3. **AWS Distributed Systems** (Whitepapers)

### Real-World Systems to Study
1. **Redis**: In-memory data structure store
2. **Cassandra**: Wide-column distributed database
3. **DynamoDB**: AWS key-value store (inspiration for this project)
4. **etcd**: Distributed key-value store for configuration

## 📊 Performance Tips for Learning

### When Testing in Colab:
```python
# 1. Use smaller datasets for quick experiments
# 2. Increase Colab RAM if needed (Runtime → Change runtime type)
# 3. Use %%time magic commands for timing
# 4. Save intermediate results to Google Drive
# 5. Use Colab forms for interactive parameter tuning

# Example timing
%%time
db = ColabDistributedDB(num_nodes=3)
for i in range(1000):
    db.put("test", f"key_{i}", {"value": i})
```

## ❓ Frequently Asked Questions

### Q: Can I use this in production?
**A**: No, this is an educational project. For production, consider Redis, Cassandra, or DynamoDB.

### Q: How is this different from Redis?
**A**: Redis is a production-ready, high-performance database. This project is a simplified implementation for learning purposes.

### Q: Can I run this outside Colab?
**A**: Yes! While designed for Colab, it runs anywhere Python 3.8+ is available.

### Q: How do I handle larger datasets?
**A**: This is an in-memory database, so dataset size is limited by RAM. For larger data, you'd need to add disk persistence.

### Q: Is there a GUI interface?
**A**: Not currently, but you could build one using Flask/Django + this database as a backend!

## 📈 Project Roadmap

### Phase 1: Core Distribution (✓ Complete)
- Basic consistent hashing
- Node discovery and clustering
- Replication mechanisms

### Phase 2: Advanced Features (In Progress)
- Secondary indexes
- Basic transaction support
- Improved query language

### Phase 3: Production Readiness (Future)
- Authentication and authorization
- Comprehensive monitoring
- Backup and restore utilities
- Performance optimizations

## 🎯 Learning Outcomes

By working with this project, you'll gain practical understanding of:

1. **Distributed Systems Fundamentals**: Consistency, availability, partitioning
2. **Database Internals**: Storage engines, indexing, query processing
3. **Network Programming**: RPC, message passing, fault tolerance
4. **System Design**: Trade-offs in distributed architectures
5. **Python Programming**: Advanced data structures, concurrency, serialization

