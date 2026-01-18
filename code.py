"""
Distributed Lightweight Database for Google Colab
Version 1.0 - Educational Purpose

This database simulates a distributed system across multiple nodes.
In a real Colab environment, nodes would be separate notebooks/Runtime sessions.
"""

import json
import time
import hashlib
import socket
import pickle
import threading
import random
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, OrderedDict
import urllib.request
import urllib.parse
import requests
import ipaddress
import asyncio
import aiohttp
from dataclasses import dataclass, field
import secrets

# ============================================
# Data Structures
# ============================================

@dataclass
class NodeInfo:
    """Information about a node in the cluster"""
    node_id: str
    address: str
    port: int
    is_active: bool = True
    last_seen: float = field(default_factory=time.time)
    shards: List[int] = field(default_factory=list)
    load: int = 0  # Number of active operations

@dataclass
class Partition:
    """Data partition/shard information"""
    partition_id: int
    key_range: Tuple[int, int]  # Consistent hashing range
    node_id: str  # Primary node
    replicas: List[str] = field(default_factory=list)  # Replica nodes
    status: str = "active"

@dataclass
class WriteAheadLogEntry:
    """WAL entry for durability"""
    operation: str  # 'SET', 'DELETE', 'CREATE_TABLE'
    key: str
    value: Any = None
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0

# ============================================
# Consistent Hashing Implementation
# ============================================

class ConsistentHashRing:
    """Consistent hashing for distributed key placement"""
    
    def __init__(self, nodes: List[str], replicas: int = 3):
        self.replicas = replicas
        self.ring = OrderedDict()
        self.nodes = set()
        
        for node in nodes:
            self.add_node(node)
    
    def _hash(self, key: str) -> int:
        """MurmurHash-like simplified hash function"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
    
    def add_node(self, node: str):
        """Add a node to the hash ring"""
        self.nodes.add(node)
        for i in range(self.replicas):
            replica_key = f"{node}:{i}"
            hash_val = self._hash(replica_key)
            self.ring[hash_val] = node
        
        # Sort the ring
        self.ring = OrderedDict(sorted(self.ring.items()))
    
    def remove_node(self, node: str):
        """Remove a node from the hash ring"""
        self.nodes.discard(node)
        for i in range(self.replicas):
            replica_key = f"{node}:{i}"
            hash_val = self._hash(replica_key)
            if hash_val in self.ring:
                del self.ring[hash_val]
    
    def get_node(self, key: str) -> str:
        """Get the node responsible for a key"""
        if not self.ring:
            return None
        
        hash_val = self._hash(key)
        
        # Find the first node with hash >= key's hash
        for node_hash in sorted(self.ring.keys()):
            if node_hash >= hash_val:
                return self.ring[node_hash]
        
        # Wrap around to the first node
        return self.ring[next(iter(self.ring))]
    
    def get_replica_nodes(self, key: str, n: int = 2) -> List[str]:
        """Get N replica nodes for a key (including primary)"""
        if not self.ring:
            return []
        
        hash_val = self._hash(key)
        nodes = []
        seen = set()
        
        sorted_hashes = sorted(self.ring.keys())
        
        # Find starting index
        start_idx = 0
        for i, node_hash in enumerate(sorted_hashes):
            if node_hash >= hash_val:
                start_idx = i
                break
        
        # Collect nodes
        for i in range(len(sorted_hashes)):
            idx = (start_idx + i) % len(sorted_hashes)
            node = self.ring[sorted_hashes[idx]]
            if node not in seen:
                nodes.append(node)
                seen.add(node)
                if len(nodes) >= n:
                    break
        
        return nodes

# ============================================
# Distributed Database Node
# ============================================

class DistributedDBNode:
    """A single node in the distributed database"""
    
    def __init__(self, node_id: str = None, port: int = 8080, 
                 discovery_url: str = None):
        self.node_id = node_id or f"node_{secrets.token_hex(4)}"
        self.port = port
        self.discovery_url = discovery_url
        
        # Local storage
        self.data = defaultdict(dict)  # {table: {key: value}}
        self.indexes = defaultdict(dict)  # {table: {column: {value: [keys]}}}
        self.write_ahead_log = []
        self.wal_sequence = 0
        
        # Cluster state
        self.hash_ring = ConsistentHashRing([])
        self.nodes: Dict[str, NodeInfo] = {}
        self.partitions: Dict[int, Partition] = {}
        self.replication_factor = 2
        
        # Network components (simulated in Colab)
        self.message_queue = asyncio.Queue()
        self.is_running = False
        
        # Thread safety
        self.locks = defaultdict(threading.RLock)
        self.partition_locks = defaultdict(threading.RLock)
        
        # Statistics
        self.stats = {
            'local_operations': 0,
            'remote_operations': 0,
            'errors': 0,
            'start_time': time.time(),
            'bytes_stored': 0
        }
        
        print(f"🔧 Node {self.node_id} initialized on port {port}")
    
    # ============================================
    # Cluster Management
    # ============================================
    
    def join_cluster(self, bootstrap_nodes: List[str] = None):
        """Join an existing cluster or start a new one"""
        if bootstrap_nodes:
            # Try to join existing cluster
            print(f"🔄 Joining cluster via bootstrap nodes: {bootstrap_nodes}")
            for node_addr in bootstrap_nodes:
                try:
                    response = self._send_http_request(
                        node_addr, '/cluster/join',
                        {'node_id': self.node_id, 'address': self.get_address()}
                    )
                    if response and response.get('success'):
                        self._update_cluster_state(response['cluster_state'])
                        print(f"✅ Joined cluster via {node_addr}")
                        return True
                except Exception as e:
                    print(f"⚠️ Failed to join via {node_addr}: {e}")
        
        # Start new cluster
        print("🚀 Starting new cluster")
        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=self.get_address(),
            port=self.port
        )
        self._rebuild_hash_ring()
        return True
    
    def leave_cluster(self):
        """Gracefully leave the cluster"""
        print(f"👋 Node {self.node_id} leaving cluster")
        
        # Notify other nodes
        for node_id, node_info in self.nodes.items():
            if node_id != self.node_id and node_info.is_active:
                try:
                    self._send_http_request(
                        f"{node_info.address}:{node_info.port}",
                        '/cluster/node_left',
                        {'node_id': self.node_id}
                    )
                except:
                    pass
        
        self.is_running = False
        return True
    
    def _update_cluster_state(self, cluster_state: Dict):
        """Update local view of cluster state"""
        self.nodes.clear()
        
        for node_data in cluster_state['nodes']:
            node_info = NodeInfo(**node_data)
            self.nodes[node_info.node_id] = node_info
        
        for partition_data in cluster_state['partitions']:
            partition = Partition(**partition_data)
            self.partitions[partition.partition_id] = partition
        
        self._rebuild_hash_ring()
    
    def _rebuild_hash_ring(self):
        """Rebuild consistent hash ring from current nodes"""
        active_nodes = [
            node_info.address + ":" + str(node_info.port)
            for node_info in self.nodes.values()
            if node_info.is_active
        ]
        self.hash_ring = ConsistentHashRing(active_nodes)
    
    # ============================================
    # Data Operations
    # ============================================
    
    def put(self, table: str, key: str, value: Any, 
            replication: str = 'quorum') -> bool:
        """
        Store a key-value pair in the distributed database
        
        replication: 'one', 'quorum', 'all'
        """
        # Determine responsible nodes
        key_str = f"{table}:{key}"
        primary_node = self.hash_ring.get_node(key_str)
        replica_nodes = self.hash_ring.get_replica_nodes(
            key_str, self.replication_factor
        )
        
        # Check if we're a responsible node
        my_address = self.get_address()
        is_responsible = my_address in [n.split(':')[0] for n in replica_nodes]
        
        if not is_responsible:
            # Forward to responsible node
            try:
                response = self._send_http_request(
                    primary_node, '/data/put',
                    {'table': table, 'key': key, 'value': value, 
                     'replication': replication}
                )
                return response.get('success', False)
            except Exception as e:
                print(f"❌ Failed to forward PUT: {e}")
                return False
        
        # We're responsible - perform local and replicated write
        success_count = 0
        
        # Local write
        with self.locks[table]:
            self.data[table][key] = value
            self._write_wal('SET', key_str, value)
            success_count += 1
        
        # Replicate to other nodes based on replication mode
        if replication in ['quorum', 'all']:
            for node_addr in replica_nodes:
                if node_addr != primary_node:
                    try:
                        self._send_http_request(
                            node_addr, '/data/replicate',
                            {'table': table, 'key': key, 'value': value,
                             'source': self.node_id}
                        )
                        success_count += 1
                    except:
                        pass
        
        # Check quorum
        if replication == 'one':
            required = 1
        elif replication == 'quorum':
            required = (self.replication_factor // 2) + 1
        else:  # 'all'
            required = len(replica_nodes)
        
        success = success_count >= required
        if success:
            self.stats['local_operations'] += 1
        
        return success
    
    def get(self, table: str, key: str, 
            consistency: str = 'quorum') -> Optional[Any]:
        """
        Retrieve a value from the distributed database
        
        consistency: 'one', 'quorum', 'all'
        """
        key_str = f"{table}:{key}"
        
        # Determine responsible nodes
        primary_node = self.hash_ring.get_node(key_str)
        replica_nodes = self.hash_ring.get_replica_nodes(
            key_str, self.replication_factor
        )
        
        # Check local cache first
        with self.locks[table]:
            if key in self.data[table]:
                return self.data[table][key]
        
        # If not local, query from cluster
        if consistency == 'one':
            # Try primary first
            try:
                response = self._send_http_request(
                    primary_node, '/data/get',
                    {'table': table, 'key': key}
                )
                if response and 'value' in response:
                    return response['value']
            except:
                pass
            
            # Try any replica
            for node_addr in replica_nodes:
                if node_addr != primary_node:
                    try:
                        response = self._send_http_request(
                            node_addr, '/data/get',
                            {'table': table, 'key': key}
                        )
                        if response and 'value' in response:
                            return response['value']
                    except:
                        pass
        
        elif consistency in ['quorum', 'all']:
            # Read from multiple nodes and resolve conflicts
            responses = []
            
            for node_addr in replica_nodes:
                try:
                    response = self._send_http_request(
                        node_addr, '/data/get',
                        {'table': table, 'key': key}
                    )
                    if response and 'value' in response:
                        responses.append(response['value'])
                except:
                    continue
            
            if not responses:
                return None
            
            if consistency == 'quorum':
                required = (self.replication_factor // 2) + 1
            else:  # 'all'
                required = len(replica_nodes)
            
            if len(responses) >= required:
                # Simple conflict resolution: return most recent (by timestamp if available)
                return max(responses, key=lambda x: 
                          x.get('_timestamp', 0) if isinstance(x, dict) else 0)
        
        return None
    
    def delete(self, table: str, key: str, 
               replication: str = 'quorum') -> bool:
        """Delete a key from the distributed database"""
        key_str = f"{table}:{key}"
        
        # Similar to put operation but with tombstone
        tombstone = {'_deleted': True, '_timestamp': time.time()}
        return self.put(table, key, tombstone, replication)
    
    def query(self, table: str, 
              conditions: Dict[str, Any] = None) -> List[Any]:
        """
        Simple distributed query with conditions
        Note: This is inefficient for large datasets - for demo only
        """
        results = []
        
        # Check local data
        with self.locks[table]:
            for key, value in self.data[table].items():
                if self._matches_conditions(value, conditions):
                    results.append({'key': key, 'value': value})
        
        # In a real distributed system, we'd need to query other nodes
        # For simplicity, we'll just use local data in this demo
        
        return results
    
    def create_table(self, table: str, schema: Dict[str, str]):
        """Create a new table with schema"""
        with self.locks[table]:
            if table not in self.data:
                self.data[table] = {}
                self.indexes[table] = {}
                
                # Broadcast to cluster
                for node_id, node_info in self.nodes.items():
                    if node_info.node_id != self.node_id and node_info.is_active:
                        try:
                            self._send_http_request(
                                f"{node_info.address}:{node_info.port}",
                                '/schema/create_table',
                                {'table': table, 'schema': schema}
                            )
                        except:
                            pass
                
                return True
        
        return False
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def _matches_conditions(self, value: Any, conditions: Dict[str, Any]) -> bool:
        """Check if value matches query conditions"""
        if not conditions:
            return True
        
        if not isinstance(value, dict):
            return False
        
        for field, expected in conditions.items():
            if field not in value or value[field] != expected:
                return False
        
        return True
    
    def _write_wal(self, operation: str, key: str, value: Any = None):
        """Write to Write-Ahead Log for durability"""
        self.wal_sequence += 1
        entry = WriteAheadLogEntry(
            operation=operation,
            key=key,
            value=value,
            timestamp=time.time(),
            sequence=self.wal_sequence
        )
        self.write_ahead_log.append(entry)
        
        # Keep WAL size limited (for demo)
        if len(self.write_ahead_log) > 1000:
            self.write_ahead_log = self.write_ahead_log[-1000:]
    
    def _send_http_request(self, address: str, endpoint: str, 
                          data: Dict) -> Optional[Dict]:
        """
        Simulate HTTP request to another node
        In real Colab, this would use actual HTTP
        For demo, we simulate with direct method calls
        """
        # Extract port if present
        if ':' in address:
            addr_parts = address.split(':')
            target_address = addr_parts[0]
            target_port = int(addr_parts[1]) if len(addr_parts) > 1 else 8080
        else:
            target_address = address
            target_port = 8080
        
        # Simulate network delay
        time.sleep(0.01)
        
        # For demo purposes, if target is ourselves, handle locally
        my_address = self.get_address()
        if target_address == my_address or address == my_address:
            return self._handle_local_request(endpoint, data)
        
        # Otherwise, simulate remote call
        # In a real implementation, this would be an actual HTTP request
        print(f"📡 Simulating request to {address}{endpoint}")
        
        # Simulate 90% success rate for demo
        if random.random() < 0.9:
            return {'success': True, 'message': 'Simulated success'}
        else:
            raise Exception("Simulated network failure")
    
    def _handle_local_request(self, endpoint: str, data: Dict) -> Dict:
        """Handle HTTP-like requests locally for simulation"""
        
        if endpoint == '/data/put':
            table = data.get('table')
            key = data.get('key')
            value = data.get('value')
            
            with self.locks[table]:
                self.data[table][key] = value
                self._write_wal('SET', f"{table}:{key}", value)
            
            return {'success': True}
        
        elif endpoint == '/data/get':
            table = data.get('table')
            key = data.get('key')
            
            with self.locks[table]:
                value = self.data[table].get(key)
            
            return {'value': value, 'success': value is not None}
        
        elif endpoint == '/cluster/join':
            # Add new node to cluster
            new_node_id = data.get('node_id')
            new_address = data.get('address')
            
            self.nodes[new_node_id] = NodeInfo(
                node_id=new_node_id,
                address=new_address,
                port=8080  # Default port
            )
            self._rebuild_hash_ring()
            
            # Return cluster state
            return {
                'success': True,
                'cluster_state': self.get_cluster_state()
            }
        
        elif endpoint == '/schema/create_table':
            table = data.get('table')
            schema = data.get('schema')
            
            if table not in self.data:
                self.data[table] = {}
                self.indexes[table] = {}
            
            return {'success': True}
        
        return {'success': False, 'error': 'Unknown endpoint'}
    
    # ============================================
    # Utility Methods
    # ============================================
    
    def get_address(self) -> str:
        """Get this node's address"""
        # In Colab, we simulate an address
        # In a real distributed system, this would be the actual IP
        return f"127.0.0.1"  # Simplified for Colab
    
    def get_cluster_state(self) -> Dict:
        """Get current cluster state"""
        nodes_list = []
        for node_info in self.nodes.values():
            nodes_list.append({
                'node_id': node_info.node_id,
                'address': node_info.address,
                'port': node_info.port,
                'is_active': node_info.is_active,
                'last_seen': node_info.last_seen,
                'shards': node_info.shards,
                'load': node_info.load
            })
        
        partitions_list = []
        for partition in self.partitions.values():
            partitions_list.append({
                'partition_id': partition.partition_id,
                'key_range': partition.key_range,
                'node_id': partition.node_id,
                'replicas': partition.replicas,
                'status': partition.status
            })
        
        return {
            'nodes': nodes_list,
            'partitions': partitions_list,
            'replication_factor': self.replication_factor,
            'timestamp': time.time()
        }
    
    def get_stats(self) -> Dict:
        """Get node statistics"""
        total_keys = sum(len(table_data) for table_data in self.data.values())
        
        return {
            'node_id': self.node_id,
            'uptime': time.time() - self.stats['start_time'],
            'local_operations': self.stats['local_operations'],
            'remote_operations': self.stats['remote_operations'],
            'errors': self.stats['errors'],
            'total_keys': total_keys,
            'tables': list(self.data.keys()),
            'wal_size': len(self.write_ahead_log),
            'cluster_size': len(self.nodes)
        }
    
    def print_status(self):
        """Print node status"""
        print(f"\n{'='*60}")
        print(f"📊 NODE STATUS: {self.node_id}")
        print(f"{'='*60}")
        
        stats = self.get_stats()
        for key, value in stats.items():
            print(f"{key:20}: {value}")
        
        print(f"\n📋 Cluster Nodes ({len(self.nodes)}):")
        for node_id, node_info in self.nodes.items():
            status = "🟢" if node_info.is_active else "🔴"
            print(f"  {status} {node_id:15} {node_info.address}:{node_info.port}")
        
        print(f"\n🗂️ Local Tables:")
        for table_name, table_data in self.data.items():
            print(f"  📁 {table_name:15} ({len(table_data)} records)")

# ============================================
# Client Interface
# ============================================

class DistributedDBClient:
    """Client interface for interacting with the distributed database"""
    
    def __init__(self, bootstrap_nodes: List[str] = None):
        self.nodes = {}
        self.current_node = None
        
        if bootstrap_nodes:
            self.connect(bootstrap_nodes)
    
    def connect(self, bootstrap_nodes: List[str]):
        """Connect to the distributed database cluster"""
        # For Colab demo, we'll create a local node
        self.current_node = DistributedDBNode(
            node_id="client_node",
            port=9090,
            discovery_url=None
        )
        
        # Join the cluster
        success = self.current_node.join_cluster(bootstrap_nodes)
        
        if success:
            print("✅ Connected to cluster")
            self.print_cluster_info()
        else:
            print("⚠️ Starting standalone mode")
        
        return success
    
    def put(self, table: str, key: str, value: Any, 
            replication: str = 'quorum') -> bool:
        """Store data in the distributed database"""
        if not self.current_node:
            print("❌ Not connected to any node")
            return False
        
        return self.current_node.put(table, key, value, replication)
    
    def get(self, table: str, key: str, 
            consistency: str = 'quorum') -> Optional[Any]:
        """Retrieve data from the distributed database"""
        if not self.current_node:
            print("❌ Not connected to any node")
            return None
        
        return self.current_node.get(table, key, consistency)
    
    def delete(self, table: str, key: str, 
               replication: str = 'quorum') -> bool:
        """Delete data from the distributed database"""
        if not self.current_node:
            print("❌ Not connected to any node")
            return False
        
        return self.current_node.delete(table, key, replication)
    
    def create_table(self, table: str, schema: Dict[str, str]) -> bool:
        """Create a new table in the distributed database"""
        if not self.current_node:
            print("❌ Not connected to any node")
            return False
        
        return self.current_node.create_table(table, schema)
    
    def query(self, table: str, 
              conditions: Dict[str, Any] = None) -> List[Any]:
        """Query data from the distributed database"""
        if not self.current_node:
            print("❌ Not connected to any node")
            return []
        
        return self.current_node.query(table, conditions)
    
    def print_cluster_info(self):
        """Print information about the cluster"""
        if self.current_node:
            self.current_node.print_status()

# ============================================
# Demo and Example Usage
# ============================================

def run_distributed_demo():
    """Run a demonstration of the distributed database"""
    print("🚀 DISTRIBUTED DATABASE DEMO")
    print("=" * 60)
    
    # Simulate a multi-node cluster
    print("\n1. Creating simulated cluster with 3 nodes...")
    
    # Create nodes (in real Colab, these would be separate notebooks)
    node1 = DistributedDBNode(node_id="node_alpha", port=8081)
    node2 = DistributedDBNode(node_id="node_beta", port=8082)
    node3 = DistributedDBNode(node_id="node_gamma", port=8083)
    
    # Start a cluster with node1 as bootstrap
    node1.join_cluster([])  # Start new cluster
    
    # Other nodes join the cluster
    node2.join_cluster(["127.0.0.1:8081"])
    node3.join_cluster(["127.0.0.1:8081"])
    
    # Create client
    print("\n2. Creating client connection...")
    client = DistributedDBClient(["127.0.0.1:8081"])
    
    # Create tables
    print("\n3. Creating distributed tables...")
    client.create_table("users", {
        "id": "int",
        "name": "str",
        "email": "str",
        "age": "int"
    })
    
    client.create_table("products", {
        "id": "int",
        "name": "str",
        "price": "float",
        "category": "str"
    })
    
    # Store data
    print("\n4. Storing distributed data...")
    
    users = [
        {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 25},
        {"id": 2, "name": "Bob", "email": "bob@example.com", "age": 30},
        {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35},
        {"id": 4, "name": "Diana", "email": "diana@example.com", "age": 28},
    ]
    
    for user in users:
        key = f"user_{user['id']}"
        success = client.put("users", key, user, replication='quorum')
        print(f"   Stored {key}: {'✅' if success else '❌'}")
    
    products = [
        {"id": 101, "name": "Laptop", "price": 999.99, "category": "Electronics"},
        {"id": 102, "name": "Mouse", "price": 29.99, "category": "Electronics"},
        {"id": 103, "name": "Desk Chair", "price": 199.99, "category": "Furniture"},
    ]
    
    for product in products:
        key = f"product_{product['id']}"
        success = client.put("products", key, product, replication='quorum')
        print(f"   Stored {key}: {'✅' if success else '❌'}")
    
    # Retrieve data
    print("\n5. Retrieving data with different consistency levels...")
    
    # Read with quorum consistency
    print("\n   Reading with QUORUM consistency:")
    user_data = client.get("users", "user_2", consistency='quorum')
    if user_data:
        print(f"   Found: {user_data['name']} ({user_data['email']})")
    else:
        print("   ❌ Data not available")
    
    # Read with one consistency
    print("\n   Reading with ONE consistency (faster but potentially stale):")
    product_data = client.get("products", "product_101", consistency='one')
    if product_data:
        print(f"   Found: {product_data['name']} - ${product_data['price']}")
    else:
        print("   ❌ Data not available")
    
    # Query data
    print("\n6. Querying data...")
    
    # Find all electronics
    electronics = client.query("products", {"category": "Electronics"})
    print(f"\n   Electronics products:")
    for item in electronics:
        print(f"   • {item['value']['name']} (${item['value']['price']})")
    
    # Find users over 30
    older_users = client.query("users", {"age": 35})  # Exact match for demo
    print(f"\n   Users aged 35:")
    for item in older_users:
        print(f"   • {item['value']['name']} ({item['value']['email']})")
    
    # Demonstrate fault tolerance
    print("\n7. Simulating node failure...")
    print("   (In a real cluster, data would still be available via replicas)")
    
    # Update data
    print("\n8. Updating distributed data...")
    updated_user = {"id": 2, "name": "Robert", "email": "bob.updated@example.com", "age": 31}
    success = client.put("users", "user_2", updated_user, replication='quorum')
    print(f"   Updated user_2: {'✅' if success else '❌'}")
    
    # Verify update
    verified_user = client.get("users", "user_2", consistency='quorum')
    if verified_user:
        print(f"   Verified: {verified_user['name']} is now {verified_user['age']} years old")
    
    # Show cluster status
    print("\n9. Cluster status:")
    client.print_cluster_info()
    
    # Show node statistics
    print("\n10. Node statistics:")
    for node in [node1, node2, node3]:
        stats = node.get_stats()
        print(f"\n   📊 {node.node_id}:")
        print(f"      Operations: {stats['local_operations']}")
        print(f"      Keys stored: {stats['total_keys']}")
        print(f"      Uptime: {stats['uptime']:.1f}s")
    
    print("\n" + "=" * 60)
    print("🎉 Distributed Database Demo Complete!")
    print("\nKey Concepts Demonstrated:")
    print("  • Consistent Hashing for data distribution")
    print("  • Replication for fault tolerance")
    print("  • Quorum-based consistency")
    print("  • Write-Ahead Logging for durability")
    print("  • Distributed query processing")
    
    return client, [node1, node2, node3]

# ============================================
# Colab-Specific Utilities
# ============================================

class ColabDistributedDB:
    """
    Simplified wrapper for Colab notebooks
    This simulates a distributed environment within a single notebook
    """
    
    def __init__(self, num_nodes: int = 3):
        self.num_nodes = num_nodes
        self.nodes = []
        self.client = None
        
        print(f"🧪 Creating {num_nodes}-node distributed database simulation")
        
        # Create nodes
        for i in range(num_nodes):
            node = DistributedDBNode(
                node_id=f"colab_node_{i+1}",
                port=8000 + i
            )
            self.nodes.append(node)
        
        # Form cluster
        if num_nodes > 0:
            self.nodes[0].join_cluster([])
            
            for i in range(1, num_nodes):
                bootstrap_addr = f"127.0.0.1:{self.nodes[0].port}"
                self.nodes[i].join_cluster([bootstrap_addr])
        
        # Create client
        self.client = DistributedDBClient([f"127.0.0.1:{self.nodes[0].port}"])
    
    def put(self, table: str, key: str, value: Any, 
            replication: str = 'quorum') -> bool:
        """Store data"""
        return self.client.put(table, key, value, replication)
    
    def get(self, table: str, key: str, 
            consistency: str = 'quorum') -> Any:
        """Retrieve data"""
        return self.client.get(table, key, consistency)
    
    def query(self, table: str, conditions: Dict = None) -> List:
        """Query data"""
        return self.client.query(table, conditions)
    
    def create_table(self, table: str, schema: Dict):
        """Create table"""
        return self.client.create_table(table, schema)
    
    def status(self):
        """Print status"""
        self.client.print_cluster_info()
    
    def demo(self):
        """Run a quick demo"""
        print("🧪 Running Colab Distributed DB Demo...")
        
        # Create table
        self.create_table("demo_data", {
            "id": "int",
            "value": "str",
            "timestamp": "float"
        })
        
        # Store some data
        for i in range(5):
            data = {
                "id": i,
                "value": f"sample_data_{i}",
                "timestamp": time.time()
            }
            success = self.put("demo_data", f"key_{i}", data)
            print(f"Stored key_{i}: {'✅' if success else '❌'}")
        
        # Retrieve data
        retrieved = self.get("demo_data", "key_2")
        print(f"\nRetrieved key_2: {retrieved}")
        
        # Query data
        results = self.query("demo_data")
        print(f"\nTotal records: {len(results)}")
        
        # Show cluster status
        print("\nCluster Status:")
        self.status()

# ============================================
# Main execution for Colab
# ============================================

if __name__ == "__main__":
    print("🔧 Distributed In-Memory Database for Google Colab")
    print("=" * 60)
    
    # For Colab, use the simplified wrapper
    print("\nOption 1: Quick Colab Demo (3 nodes)")
    print("Option 2: Full Distributed Demo")
    
    # Uncomment to run quick demo
    # db = ColabDistributedDB(num_nodes=3)
    # db.demo()
    
    # Or run full demo
    print("\nTo run the full demo, call: run_distributed_demo()")
    print("Example:")
    print("  client, nodes = run_distributed_demo()")
    print("  client.put('my_table', 'key1', {'name': 'test'})")
    print("  client.get('my_table', 'key1')")
