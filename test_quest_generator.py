"""
Test script for Stage 10: Procedural Quest Generator

Run this after starting the server to test quest generation.
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


def test_quest_types():
    """Test getting all quest types."""
    print_section("TEST 1: Get Quest Types")
    
    response = requests.get(f"{BASE_URL}/quest/types")
    data = response.json()
    
    print(f"Total quest types: {data['total_types']}")
    print("\nQuest Types:")
    for qt in data['quest_types'][:5]:  # Show first 5
        print(f"  - {qt['type'].upper()}: {qt['description']}")
        print(f"    Best for: {', '.join(qt['best_for'])}")
    
    return response.status_code == 200


def test_generate_single_quest(player_id, world_id, location_id):
    """Test generating a single personalized quest."""
    print_section("TEST 2: Generate Single Quest")
    
    print(f"Generating quest for player {player_id}...")
    
    response = requests.post(
        f"{BASE_URL}/quest/generate/{player_id}",
        params={
            "world_id": world_id,
            "location_id": location_id,
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False
    
    quest = response.json()
    
    print(f"✅ Quest Generated!")
    print(f"\nQuest ID: {quest.get('id')}")
    print(f"Title: {quest.get('title')}")
    print(f"Type: {quest.get('quest_type')}")
    print(f"Difficulty: {quest.get('difficulty')}")
    print(f"\nDescription:")
    print(f"  {quest.get('description')}")
    print(f"\nObjectives:")
    for i, obj in enumerate(quest.get('objectives', []), 1):
        print(f"  {i}. {obj}")
    print(f"\nRewards:")
    rewards = quest.get('rewards', {})
    print(f"  Gold: {rewards.get('gold', 0)}")
    print(f"  Experience: {rewards.get('experience', 0)}")
    
    if quest.get('quest_giver_dialogue'):
        dialogue = quest['quest_giver_dialogue']
        print(f"\nQuest Giver Says:")
        print(f"  \"{dialogue.get('introduction', 'N/A')[:100]}...\"")
    
    return quest.get('id')


def test_generate_quest_chain(player_id, world_id, location_id):
    """Test generating a quest chain."""
    print_section("TEST 3: Generate Quest Chain")
    
    print(f"Generating 3-quest chain for player {player_id}...")
    
    response = requests.post(
        f"{BASE_URL}/quest/generate-chain/{player_id}",
        params={
            "world_id": world_id,
            "location_id": location_id,
            "chain_length": 3,
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False
    
    data = response.json()
    
    print(f"✅ Quest Chain Generated!")
    print(f"\nChain Length: {data['chain_length']}")
    print(f"\nQuests in Chain:")
    
    for quest in data['quests']:
        print(f"\n  {quest.get('chain_position')}. {quest.get('title')}")
        print(f"     Type: {quest.get('quest_type')} | Difficulty: {quest.get('difficulty')}")
        print(f"     Unlocks: Quest {quest.get('unlocks_quest', 'None (Final)')}")
    
    return data['quests'][0].get('id') if data['quests'] else None


def test_get_active_quests(player_id, world_id):
    """Test getting active quests."""
    print_section("TEST 4: Get Active Quests")
    
    response = requests.get(
        f"{BASE_URL}/quest/active/{player_id}",
        params={"world_id": world_id}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return False
    
    data = response.json()
    
    print(f"✅ Active Quests Retrieved!")
    print(f"\nTotal Active Quests: {data['total_quests']}")
    
    if data['quests']:
        print("\nActive Quests:")
        for quest in data['quests'][:3]:  # Show first 3
            print(f"  - [{quest['id']}] {quest['title']}")
            print(f"    Type: {quest['type']} | State: {quest['state']}")
    else:
        print("\nNo active quests.")
    
    return True


def test_complete_quest(quest_id, player_id, world_id):
    """Test completing a quest."""
    print_section("TEST 5: Complete Quest")
    
    if not quest_id:
        print("⚠️  No quest ID provided, skipping test")
        return False
    
    print(f"Completing quest {quest_id} with diplomatic approach...")
    
    response = requests.post(
        f"{BASE_URL}/quest/complete/{quest_id}",
        params={
            "player_id": player_id,
            "world_id": world_id,
            "completion_method": "diplomatic",
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    
    print(f"✅ Quest Completed!")
    print(f"\nQuest: {result.get('quest_title')}")
    print(f"Completion Method: {result.get('completion_method')}")
    print(f"\nRewards Granted:")
    rewards = result.get('rewards_granted', {})
    print(f"  Gold: +{rewards.get('gold', 0)}")
    print(f"  Experience: +{rewards.get('experience', 0)}")
    
    rep_changes = rewards.get('reputation_changes', {})
    if rep_changes:
        print(f"  Reputation Changes:")
        for faction_id, change in rep_changes.items():
            print(f"    Faction {faction_id}: {'+' if change > 0 else ''}{change}")
    
    return True


def test_specific_quest_type(player_id, world_id, location_id, quest_type):
    """Test generating a specific quest type."""
    print_section(f"TEST 6: Generate {quest_type.upper()} Quest")
    
    print(f"Generating {quest_type} quest...")
    
    response = requests.post(
        f"{BASE_URL}/quest/generate/{player_id}",
        params={
            "world_id": world_id,
            "location_id": location_id,
            "quest_type": quest_type,
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return False
    
    quest = response.json()
    
    print(f"✅ {quest_type.upper()} Quest Generated!")
    print(f"\nTitle: {quest.get('title')}")
    print(f"Type: {quest.get('quest_type')}")
    print(f"Description: {quest.get('description')[:100]}...")
    
    return True


def test_available_quests_at_location(location_id, world_id):
    """Test getting available quests at a location."""
    print_section("TEST 7: Get Quests at Location")
    
    response = requests.get(
        f"{BASE_URL}/quest/available/{location_id}",
        params={"world_id": world_id}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return False
    
    data = response.json()
    
    print(f"✅ Location Quests Retrieved!")
    print(f"\nLocation ID: {data['location_id']}")
    print(f"Total Quests: {data['total_quests']}")
    
    if data['quests']:
        print("\nAvailable Quests:")
        for quest in data['quests'][:3]:
            print(f"  - [{quest['id']}] {quest['title']}")
            print(f"    Type: {quest['type']}")
    
    return True


def run_all_tests():
    """Run all quest generator tests."""
    print("\n" + "🎮" * 30)
    print("  STAGE 10: QUEST GENERATOR TEST SUITE")
    print("🎮" * 30)
    
    # Configuration
    player_id = 1
    world_id = 1
    location_id = 1
    
    print(f"\nTest Configuration:")
    print(f"  Player ID: {player_id}")
    print(f"  World ID: {world_id}")
    print(f"  Location ID: {location_id}")
    
    results = []
    
    # Test 1: Quest Types
    try:
        results.append(("Quest Types", test_quest_types()))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Quest Types", False))
    
    time.sleep(1)
    
    # Test 2: Single Quest
    quest_id = None
    try:
        quest_id = test_generate_single_quest(player_id, world_id, location_id)
        results.append(("Single Quest", quest_id is not None))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Single Quest", False))
    
    time.sleep(1)
    
    # Test 3: Quest Chain
    chain_quest_id = None
    try:
        chain_quest_id = test_generate_quest_chain(player_id, world_id, location_id)
        results.append(("Quest Chain", chain_quest_id is not None))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Quest Chain", False))
    
    time.sleep(1)
    
    # Test 4: Active Quests
    try:
        results.append(("Active Quests", test_get_active_quests(player_id, world_id)))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Active Quests", False))
    
    time.sleep(1)
    
    # Test 5: Complete Quest
    try:
        results.append(("Complete Quest", test_complete_quest(quest_id, player_id, world_id)))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Complete Quest", False))
    
    time.sleep(1)
    
    # Test 6: Specific Type
    try:
        results.append(("Investigate Quest", test_specific_quest_type(
            player_id, world_id, location_id, "investigate"
        )))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Investigate Quest", False))
    
    time.sleep(1)
    
    # Test 7: Location Quests
    try:
        results.append(("Location Quests", test_available_quests_at_location(location_id, world_id)))
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append(("Location Quests", False))
    
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
        print("🎉 All tests passed! Quest Generator is working perfectly!")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Check the output above.")
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print("\n⚠️  Make sure the server is running:")
    print("   uvicorn backend.main:app --reload\n")
    
    input("Press Enter to start tests...")
    
    try:
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to server.")
        print("   Make sure the server is running on http://localhost:8000")
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user.")
