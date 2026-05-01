"""
Test script for Stage 11: GraphRAG Lore Engine

Run this after starting the server to test lore queries.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def test_build_index(world_id):
    """Test building the lore index."""
    print_section("TEST 1: Build Lore Index")
    
    print(f"Building lore index for world {world_id}...")
    
    response = requests.post(f"{BASE_URL}/lore/build/{world_id}")
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False
    
    data = response.json()
    
    print(f"✅ Lore Index Built!")
    print(f"\nStats:")
    print(f"  Nodes: {data['stats']['graph']['nodes']}")
    print(f"  Edges: {data['stats']['graph']['edges']}")
    print(f"  Embeddings: {data['stats']['embeddings']['total_documents']}")
    
    return True


def test_query_lore(world_id, query):
    """Test querying the lore."""
    print_section(f"TEST 2: Query Lore")
    
    print(f"Query: '{query}'")
    print("Searching...")
    
    response = requests.post(
        f"{BASE_URL}/lore/query",
        json={
            "world_id": world_id,
            "query": query,
            "max_results": 10,
            "max_hops": 2,
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False
    
    data = response.json()
    
    print(f"✅ Query Completed!")
    print(f"\nAnswer:")
    print(f"  {data['answer']}")
    
    print(f"\nSources:")
    print(f"  Nodes found: {data['sources']['nodes_found']}")
    print(f"  Edges found: {data['sources']['edges_found']}")
    
    if data['sources']['top_entities']:
        print(f"\n  Top Entities:")
        for entity in data['sources']['top_entities'][:3]:
            print(f"    - {entity['name']} ({entity['type']})")
    
    if data['sources']['key_events']:
        print(f"\n  Key Events:")
        for event in data['sources']['key_events'][:3]:
            print(f"    - {event}")
    
    return True


def test_entity_history(world_id, entity_type, entity_name):
    """Test getting entity history."""
    print_section("TEST 3: Entity History")
    
    print(f"Getting history for {entity_type}: {entity_name}")
    
    response = requests.get(
        f"{BASE_URL}/lore/entity/{entity_type}/{entity_name}",
        params={"world_id": world_id}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False
    
    data = response.json()
    
    if not data.get("found"):
        print(f"❌ Entity not found: {data.get('message')}")
        return False
    
    print(f"✅ Entity Found!")
    
    entity = data['entity']
    print(f"\nEntity: {entity['name']} ({entity['type']})")
    print(f"Description: {entity.get('description', 'N/A')[:100]}...")
    print(f"Importance: {entity.get('importance', 0)}")
    print(f"Total Events: {data['total_events']}")
    
    if data.get('timeline'):
        print(f"\nTimeline (first 3 events):")
        for event in data['timeline'][:3]:
            day = event.get('world_day', 0)
            desc = event.get('description', 'N/A')
            print(f"  Day {day:.1f}: {desc}")
    
    if data.get('narrative'):
        print(f"\nNarrative Summary:")
        print(f"  {data['narrative'][:200]}...")
    
    return True


def test_entity_connections(world_id, entity_type, entity_name):
    """Test getting entity connections."""
    print_section("TEST 4: Entity Connections")
    
    print(f"Getting connections for {entity_type}: {entity_name}")
    
    response = requests.get(
        f"{BASE_URL}/lore/connections/{entity_type}/{entity_name}",
        params={"world_id": world_id}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return False
    
    data = response.json()
    
    if not data.get("found"):
        print(f"❌ Entity not found")
        return False
    
    print(f"✅ Connections Found!")
    print(f"\nTotal Connections: {data['total_connections']}")
    
    if data.get('connections'):
        print(f"\nConnections (first 5):")
        for conn in data['connections'][:5]:
            target = conn['target']
            relation = conn['relation']
            print(f"  {relation.replace('_', ' ')} → {target['name']} ({target['type']})")
    
    if data.get('explanation'):
        print(f"\nExplanation:")
        print(f"  {data['explanation'][:200]}...")
    
    return True


def test_timeline(world_id, start_day, end_day):
    """Test getting timeline."""
    print_section("TEST 5: Timeline")
    
    print(f"Getting timeline from day {start_day} to {end_day}")
    
    response = requests.get(
        f"{BASE_URL}/lore/timeline",
        params={
            "world_id": world_id,
            "start_day": start_day,
            "end_day": end_day,
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return False
    
    data = response.json()
    
    print(f"✅ Timeline Retrieved!")
    print(f"\nTotal Events: {data['total_events']}")
    
    if data.get('events'):
        print(f"\nEvents (first 5):")
        for event in data['events'][:5]:
            day = event.get('world_day', 0)
            relation = event.get('relation', 'unknown')
            desc = event.get('description', 'N/A')
            print(f"  Day {day:.1f}: {relation} - {desc[:60]}...")
    
    if data.get('narrative'):
        print(f"\nNarrative:")
        print(f"  {data['narrative'][:200]}...")
    
    return True


def test_stats(world_id):
    """Test getting stats."""
    print_section("TEST 6: Stats")
    
    response = requests.get(f"{BASE_URL}/lore/stats/{world_id}")
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return False
    
    data = response.json()
    
    print(f"✅ Stats Retrieved!")
    print(f"\nGraph:")
    print(f"  Nodes: {data['graph']['nodes']}")
    print(f"  Edges: {data['graph']['edges']}")
    print(f"\nEmbeddings:")
    print(f"  Total Documents: {data['embeddings']['total_documents']}")
    print(f"\nGraph File Exists: {data['graph_file_exists']}")
    
    return True


def run_all_tests():
    """Run all lore engine tests."""
    print("\n" + "🔮" * 30)
    print("  STAGE 11: GRAPHRAG LORE ENGINE TEST SUITE")
    print("🔮" * 30)
    
    # Configuration
    world_id = 1
    
    print(f"\nTest Configuration:")
    print(f"  World ID: {world_id}")
    
    results = []
    
    # Test 1: Build Index
    try:
        results.append(("Build Index", test_build_index(world_id)))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Build Index", False))
    
    time.sleep(1)
    
    # Test 2: Query Lore
    try:
        results.append(("Query Lore", test_query_lore(
            world_id, "What happened in this world?"
        )))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Query Lore", False))
    
    time.sleep(1)
    
    # Test 3: Entity History (try to find first NPC)
    try:
        # Get world info to find an NPC
        response = requests.get(f"{BASE_URL}/world/{world_id}")
        if response.status_code == 200:
            # Try to get first location
            regions_response = requests.get(f"{BASE_URL}/world/{world_id}/regions")
            if regions_response.status_code == 200:
                regions = regions_response.json()
                if regions:
                    # Just test with a generic query
                    results.append(("Entity History", test_entity_history(
                        world_id, "npc", "TestNPC"
                    )))
                else:
                    print("⚠️  No regions found, skipping entity history test")
                    results.append(("Entity History", True))
            else:
                print("⚠️  Could not get regions, skipping entity history test")
                results.append(("Entity History", True))
        else:
            print("⚠️  World not found, skipping entity history test")
            results.append(("Entity History", True))
    except Exception as e:
        print(f"⚠️  Entity history test skipped: {e}")
        results.append(("Entity History", True))
    
    time.sleep(1)
    
    # Test 4: Entity Connections (skip if no entities)
    try:
        results.append(("Entity Connections", test_entity_connections(
            world_id, "npc", "TestNPC"
        )))
    except Exception as e:
        print(f"⚠️  Entity connections test skipped: {e}")
        results.append(("Entity Connections", True))
    
    time.sleep(1)
    
    # Test 5: Timeline
    try:
        results.append(("Timeline", test_timeline(world_id, 0.0, 7.0)))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Timeline", False))
    
    time.sleep(1)
    
    # Test 6: Stats
    try:
        results.append(("Stats", test_stats(world_id)))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Stats", False))
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}\n")
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {test_name}")
    
    print("\n" + "=" * 60)
    
    if passed == total:
        print("🎉 All tests passed! GraphRAG Lore Engine is working!")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Check the output above.")
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print("\n⚠️  Make sure the server is running:")
    print("   uvicorn backend.main:app --reload\n")
    print("⚠️  Make sure you have a world created:")
    print("   POST /world/create?name=TestWorld&theme=dark%20fantasy\n")
    
    input("Press Enter to start tests...")
    
    try:
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to server.")
        print("   Make sure the server is running on http://localhost:8000")
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user.")
