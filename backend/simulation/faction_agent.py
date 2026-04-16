import json
import random
from backend.llm_client import chat_completion_json
from backend.database.db import SessionLocal, Faction, FactionRelationship
from backend.database.world_store import (
    get_factions, record_event, get_world,
    get_regions, get_locations, update_global_state,
)
from backend.procedural.world_context import build_world_context_string
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("simulation.faction")

# Faction type → decision weights
# How much each faction type values each resource
FACTION_PRIORITIES = {
    "kingdom": {
        "territory": 0.35,
        "military": 0.30,
        "wealth": 0.20,
        "influence": 0.15,
    },
    "guild": {
        "wealth": 0.40,
        "influence": 0.30,
        "territory": 0.15,
        "military": 0.15,
    },
    "cult": {
        "influence": 0.40,
        "wealth": 0.25,
        "territory": 0.20,
        "military": 0.15,
    },
    "tribe": {
        "military": 0.35,
        "territory": 0.30,
        "wealth": 0.20,
        "influence": 0.15,
    },
    "merchant_company": {
        "wealth": 0.45,
        "influence": 0.25,
        "territory": 0.20,
        "military": 0.10,
    },
}

# Possible faction actions by type
FACTION_ACTIONS = {
    "kingdom": [
        "claim_territory",
        "raise_taxes",
        "build_fortification",
        "recruit_soldiers",
        "sign_alliance",
        "declare_war",
        "send_diplomats",
    ],
    "guild": [
        "establish_trade_route",
        "manipulate_prices",
        "bribe_official",
        "expand_operations",
        "hire_spies",
        "corner_market",
        "fund_expedition",
    ],
    "cult": [
        "recruit_members",
        "gather_intelligence",
        "sabotage_rival",
        "spread_influence",
        "perform_ritual",
        "blackmail_official",
        "establish_safe_house",
    ],
    "tribe": [
        "raid_settlement",
        "fortify_territory",
        "seek_alliance",
        "gather_resources",
        "challenge_rival",
        "migrate_territory",
        "train_warriors",
    ],
    "merchant_company": [
        "open_trade_route",
        "price_manipulation",
        "expand_warehouse",
        "hire_guards",
        "fund_expedition",
        "corner_market",
        "bribe_customs",
    ],
}

# Resource changes per action
ACTION_RESOURCE_EFFECTS = {
    "claim_territory": {
        "military_strength": -30,
        "political_influence": +20,
        "wealth": -200,
    },
    "raise_taxes": {
        "wealth": +500,
        "political_influence": -15,
    },
    "build_fortification": {
        "military_strength": +40,
        "wealth": -400,
    },
    "recruit_soldiers": {
        "military_strength": +50,
        "wealth": -300,
    },
    "sign_alliance": {
        "political_influence": +25,
        "military_strength": +20,
    },
    "declare_war": {
        "military_strength": -20,
        "political_influence": -10,
        "wealth": -300,
    },
    "establish_trade_route": {
        "wealth": +400,
        "political_influence": +10,
    },
    "manipulate_prices": {
        "wealth": +300,
        "political_influence": -5,
    },
    "bribe_official": {
        "wealth": -200,
        "political_influence": +30,
    },
    "expand_operations": {
        "wealth": -300,
        "political_influence": +20,
    },
    "recruit_members": {
        "wealth": -100,
        "political_influence": +15,
    },
    "gather_intelligence": {
        "wealth": -150,
        "political_influence": +20,
    },
    "sabotage_rival": {
        "wealth": -100,
        "political_influence": +15,
        "military_strength": +10,
    },
    "raid_settlement": {
        "military_strength": -20,
        "wealth": +300,
        "political_influence": -20,
    },
    "fortify_territory": {
        "military_strength": +30,
        "wealth": -200,
    },
    "open_trade_route": {
        "wealth": +350,
        "political_influence": +15,
    },
    "price_manipulation": {
        "wealth": +250,
        "political_influence": -10,
    },
    "fund_expedition": {
        "wealth": -400,
        "political_influence": +15,
    },
    "train_warriors": {
        "military_strength": +45,
        "wealth": -250,
    },
    "send_diplomats": {
        "political_influence": +30,
        "wealth": -100,
    },
    "spread_influence": {
        "political_influence": +25,
        "wealth": -100,
    },
    "gather_resources": {
        "wealth": +200,
    },
}


def evaluate_faction_situation(faction: Faction) -> dict:
    """
    Evaluates a faction's current situation and determines
    what they should prioritize this tick.

    Returns priority scores for different action categories.
    """
    priorities = FACTION_PRIORITIES.get(
        faction.faction_type,
        FACTION_PRIORITIES["kingdom"],
    )

    situation = {
        "wealth_pressure": 0.0,
        "military_pressure": 0.0,
        "influence_pressure": 0.0,
        "recommended_actions": [],
    }

    # Wealth pressure — low wealth = high pressure to gain more
    if faction.wealth < 500:
        situation["wealth_pressure"] = 0.9
    elif faction.wealth < 1500:
        situation["wealth_pressure"] = 0.5
    else:
        situation["wealth_pressure"] = 0.2

    # Military pressure
    if faction.military_strength < 50:
        situation["military_pressure"] = 0.9
    elif faction.military_strength < 150:
        situation["military_pressure"] = 0.5
    else:
        situation["military_pressure"] = 0.2

    # Influence pressure
    if faction.political_influence < 20:
        situation["influence_pressure"] = 0.8
    elif faction.political_influence < 60:
        situation["influence_pressure"] = 0.4
    else:
        situation["influence_pressure"] = 0.1

    # Recommend actions based on pressure + faction type
    actions = FACTION_ACTIONS.get(
        faction.faction_type,
        FACTION_ACTIONS["kingdom"],
    )

    if situation["wealth_pressure"] > 0.6:
        wealth_actions = [
            a for a in actions
            if ACTION_RESOURCE_EFFECTS.get(a, {}).get("wealth", 0) > 0
        ]
        situation["recommended_actions"].extend(wealth_actions[:2])

    if situation["military_pressure"] > 0.6:
        mil_actions = [
            a for a in actions
            if ACTION_RESOURCE_EFFECTS.get(
                a, {}
            ).get("military_strength", 0) > 0
        ]
        situation["recommended_actions"].extend(mil_actions[:2])

    if not situation["recommended_actions"]:
        situation["recommended_actions"] = random.sample(
            actions, min(3, len(actions))
        )

    return situation


def run_faction_turn(
    world_id: int,
    faction_id: int,
) -> dict:
    """
    Runs one autonomous decision turn for a faction.

    The faction:
    1. Evaluates its situation
    2. Selects the best action
    3. Applies resource changes
    4. Generates a world event
    5. May update relations with other factions

    Returns the action taken and its effects.
    """
    db = SessionLocal()
    try:
        faction = db.query(Faction).filter(
            Faction.id == faction_id,
            Faction.is_active == True,
        ).first()

        if not faction:
            return {}

        world_time = get_current_world_time(world_id)
        situation = evaluate_faction_situation(faction)

        # Select action
        recommended = situation["recommended_actions"]
        if recommended:
            chosen_action = random.choice(recommended)
        else:
            available_actions = FACTION_ACTIONS.get(
                faction.faction_type, ["gather_resources"]
            )
            chosen_action = random.choice(available_actions)

        # Apply resource effects
        effects = ACTION_RESOURCE_EFFECTS.get(chosen_action, {})

        faction.wealth = max(0, faction.wealth + effects.get("wealth", 0))
        faction.military_strength = max(
            10,
            faction.military_strength +
            effects.get("military_strength", 0)
        )
        faction.political_influence = max(
            0,
            faction.political_influence +
            effects.get("political_influence", 0)
        )

        db.commit()

        # Generate event description
        event_description = _generate_action_description(
            faction.name,
            chosen_action,
            effects,
        )

        # Record world event
        is_notable = chosen_action in [
            "declare_war", "sign_alliance", "claim_territory",
            "raid_settlement", "sabotage_rival",
        ]

        record_event(
            world_id=world_id,
            event_type="faction_action",
            title=f"{faction.name}: {chosen_action.replace('_', ' ').title()}",
            description=event_description,
            world_day=world_time.get("total_days", 0.0),
            faction_id=faction_id,
            is_notable=is_notable,
            importance=7 if is_notable else 3,
        )

        logger.info(
            f"Faction turn | "
            f"faction='{faction.name}' | "
            f"action={chosen_action} | "
            f"wealth={faction.wealth} | "
            f"military={faction.military_strength}"
        )

        return {
            "faction_id": faction_id,
            "faction_name": faction.name,
            "action_taken": chosen_action,
            "description": event_description,
            "resource_changes": effects,
            "new_resources": {
                "wealth": faction.wealth,
                "military_strength": faction.military_strength,
                "political_influence": faction.political_influence,
            },
            "is_notable": is_notable,
        }

    finally:
        db.close()


def update_faction_relations(world_id: int):
    """
    Updates relations between all faction pairs based on
    their recent actions and world state.

    Called every few ticks to shift political landscape.
    """
    db = SessionLocal()
    try:
        factions = db.query(Faction).filter(
            Faction.world_id == world_id,
            Faction.is_active == True,
        ).all()

        changes = []

        for i, faction_a in enumerate(factions):
            for faction_b in factions[i+1:]:
                # Check existing relation
                relation = db.query(FactionRelationship).filter(
                    FactionRelationship.world_id == world_id,
                    FactionRelationship.faction_a_id == faction_a.id,
                    FactionRelationship.faction_b_id == faction_b.id,
                ).first()

                if not relation:
                    # Create new relation
                    relation = FactionRelationship(
                        world_id=world_id,
                        faction_a_id=faction_a.id,
                        faction_b_id=faction_b.id,
                        relation="neutral",
                        relation_score=0.0,
                        history=json.dumps([]),
                    )
                    db.add(relation)

                # Relations drift based on faction type conflicts
                delta = _calculate_relation_drift(
                    faction_a, faction_b
                )
                new_score = max(
                    -100,
                    min(100, relation.relation_score + delta)
                )
                relation.relation_score = new_score
                relation.relation = _score_to_relation(new_score)

                # Update history
                history = json.loads(relation.history or "[]")
                history.append({
                    "score": new_score,
                    "delta": delta,
                    "world_day": get_current_world_time(
                        world_id
                    ).get("total_days", 0),
                })
                relation.history = json.dumps(history[-20:])

                if abs(delta) > 5:
                    changes.append({
                        "faction_a": faction_a.name,
                        "faction_b": faction_b.name,
                        "new_relation": relation.relation,
                        "score": new_score,
                    })

        db.commit()
        logger.info(
            f"Faction relations updated | "
            f"changes={len(changes)}"
        )
        return changes

    finally:
        db.close()


def _calculate_relation_drift(
    faction_a: Faction,
    faction_b: Faction,
) -> float:
    """
    Calculates how much faction relations drift each tick.
    Based on faction type compatibility and resource competition.
    """
    drift = random.uniform(-3, 3)

    # Kingdoms and cults naturally drift apart
    if (faction_a.faction_type == "kingdom" and
            faction_b.faction_type == "cult"):
        drift -= 2

    # Guilds and kingdoms can cooperate
    if (faction_a.faction_type in ["kingdom", "guild"] and
            faction_b.faction_type in ["kingdom", "guild"]):
        drift += 1

    # Resource competition increases tension
    if faction_a.wealth > 3000 and faction_b.wealth > 3000:
        drift -= 1.5

    if faction_a.military_strength > 300:
        drift -= 1

    return round(drift, 2)


def _score_to_relation(score: float) -> str:
    if score >= 60:
        return "allied"
    elif score >= 30:
        return "friendly"
    elif score >= -20:
        return "neutral"
    elif score >= -50:
        return "unfriendly"
    elif score >= -75:
        return "hostile"
    else:
        return "at_war"


def _generate_action_description(
    faction_name: str,
    action: str,
    effects: dict,
) -> str:
    """Generates a readable description of a faction action."""
    templates = {
        "claim_territory": (
            f"{faction_name} has dispatched forces to claim "
            f"a new territory, expanding their domain."
        ),
        "raise_taxes": (
            f"{faction_name} has raised taxes across their "
            f"territories, filling their coffers."
        ),
        "build_fortification": (
            f"{faction_name} constructs new fortifications, "
            f"strengthening their defensive position."
        ),
        "recruit_soldiers": (
            f"{faction_name} is actively recruiting soldiers, "
            f"bolstering their military forces."
        ),
        "sign_alliance": (
            f"{faction_name} has formalized an alliance, "
            f"strengthening their political position."
        ),
        "declare_war": (
            f"{faction_name} has declared war, mobilizing "
            f"their forces for open conflict."
        ),
        "establish_trade_route": (
            f"{faction_name} establishes a new trade route, "
            f"increasing commerce and revenue."
        ),
        "manipulate_prices": (
            f"{faction_name} manipulates market prices, "
            f"gaining advantage in trade."
        ),
        "bribe_official": (
            f"{faction_name} secures political favor through "
            f"strategic payments to key officials."
        ),
        "recruit_members": (
            f"{faction_name} quietly expands their membership, "
            f"growing their influence."
        ),
        "sabotage_rival": (
            f"{faction_name} conducts covert operations against "
            f"a rival, undermining their operations."
        ),
        "raid_settlement": (
            f"{faction_name} raids a nearby settlement, "
            f"seizing resources by force."
        ),
        "gather_resources": (
            f"{faction_name} focuses on gathering resources "
            f"and consolidating their position."
        ),
        "train_warriors": (
            f"{faction_name} intensifies warrior training, "
            f"producing more formidable fighters."
        ),
    }

    return templates.get(
        action,
        f"{faction_name} takes strategic action: "
        f"{action.replace('_', ' ')}.",
    )