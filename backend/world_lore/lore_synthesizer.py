"""
LLM-powered synthesis of retrieved graph information into natural language answers.
"""
import json
from typing import Dict, List
from backend.llm_client import chat_completion
from backend.logger import get_logger

logger = get_logger("world_lore.synthesizer")


class LoreSynthesizer:
    """
    Synthesizes retrieved graph information into coherent narratives.
    
    Takes raw graph data (nodes, edges, paths) and generates:
    - Natural language answers to queries
    - Chronological narratives
    - Entity summaries
    - Relationship explanations
    """
    
    def synthesize_query_answer(
        self,
        query: str,
        retrieval_result: Dict
    ) -> str:
        """
        Synthesizes a natural language answer from retrieval results.
        
        Args:
            query: Original user query
            retrieval_result: Dict from LoreRetriever.retrieve()
            
        Returns:
            Natural language answer
        """
        logger.info(f"Synthesizing answer | query='{query[:50]}...'")
        
        # Build context from retrieval results
        context = self._build_context(retrieval_result)
        
        # Build prompt
        prompt = f"""You are a lore keeper for a fantasy world. Answer the user's question using ONLY the provided world information.

USER QUESTION:
{query}

WORLD INFORMATION:
{context}

INSTRUCTIONS:
1. Answer the question directly and concisely
2. Use only information from the provided context
3. If information is incomplete, say so
4. Mention specific names, locations, and events
5. Present information chronologically when relevant
6. If the question cannot be answered with the given information, say "I don't have enough information about that"

ANSWER:"""
        
        messages = [
            {
                "role": "system",
                "content": "You are a knowledgeable lore keeper who answers questions about a fantasy world's history and events."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            answer = chat_completion(messages, max_tokens=500, temperature=0.7)
            logger.info(f"Answer synthesized | length={len(answer)}")
            return answer.strip()
        
        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            return "I apologize, but I'm having trouble accessing the world's memories right now."
    
    def _build_context(self, retrieval_result: Dict) -> str:
        """Build context string from retrieval results."""
        context_parts = []
        
        # Add top nodes
        if retrieval_result.get("top_nodes"):
            context_parts.append("ENTITIES:")
            for node in retrieval_result["top_nodes"][:5]:
                context_parts.append(
                    f"- {node['name']} ({node['entity_type']}): "
                    f"{node.get('description', 'No description')[:150]}"
                )
        
        # Add edges (events)
        if retrieval_result.get("edges"):
            context_parts.append("\nEVENTS:")
            for edge in retrieval_result["edges"][:10]:
                if edge.get("description"):
                    day_info = f" (Day {edge['world_day']:.1f})" if edge.get("world_day") else ""
                    context_parts.append(
                        f"- {edge['description']}{day_info}"
                    )
        
        # Add paths (connections)
        if retrieval_result.get("paths"):
            context_parts.append("\nCONNECTIONS:")
            for path in retrieval_result["paths"][:3]:
                context_parts.append(
                    f"- {path['description']}"
                )
        
        return "\n".join(context_parts)
    
    def synthesize_entity_summary(
        self,
        entity_history: Dict
    ) -> str:
        """
        Synthesizes a narrative summary of an entity's history.
        
        Args:
            entity_history: Dict from LoreRetriever.retrieve_entity_history()
            
        Returns:
            Narrative summary
        """
        if not entity_history.get("found"):
            return entity_history.get("message", "Entity not found")
        
        entity = entity_history["entity"]
        timeline = entity_history.get("timeline", [])
        
        # Build timeline context
        timeline_text = []
        for event in timeline[:15]:
            day = event.get("world_day", 0)
            desc = event.get("description", "")
            timeline_text.append(f"Day {day:.1f}: {desc}")
        
        prompt = f"""Summarize the history of this entity in 2-3 paragraphs.

ENTITY:
Name: {entity['name']}
Type: {entity['type']}
Description: {entity.get('description', 'No description')}

CHRONOLOGICAL EVENTS:
{chr(10).join(timeline_text)}

Write a narrative summary that:
1. Introduces the entity
2. Describes key events in their history
3. Mentions their current status or situation
4. Uses past tense for completed events

SUMMARY:"""
        
        messages = [
            {
                "role": "system",
                "content": "You are a historian writing narrative summaries of people, places, and events."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            summary = chat_completion(messages, max_tokens=400, temperature=0.7)
            return summary.strip()
        except Exception as e:
            logger.error(f"Entity summary failed: {e}")
            return f"Unable to generate summary for {entity['name']}"
    
    def synthesize_timeline_narrative(
        self,
        time_period_result: Dict
    ) -> str:
        """
        Synthesizes a narrative of events in a time period.
        
        Args:
            time_period_result: Dict from LoreRetriever.retrieve_by_time_period()
            
        Returns:
            Chronological narrative
        """
        events = time_period_result.get("events", [])
        start_day = time_period_result.get("start_day", 0)
        end_day = time_period_result.get("end_day", 0)
        
        if not events:
            return f"No significant events occurred between day {start_day:.1f} and {end_day:.1f}."
        
        # Build event list
        event_text = []
        for event in events[:20]:
            day = event.get("world_day", 0)
            desc = event.get("description", "")
            source = event.get("source", {}).get("name", "Unknown")
            target = event.get("target", {}).get("name", "Unknown")
            relation = event.get("relation", "")
            
            event_text.append(
                f"Day {day:.1f}: {source} {relation.replace('_', ' ')} {target}. {desc}"
            )
        
        prompt = f"""Write a narrative summary of these events in chronological order.

TIME PERIOD: Day {start_day:.1f} to Day {end_day:.1f}

EVENTS:
{chr(10).join(event_text)}

Write a 2-3 paragraph narrative that:
1. Describes the major events in order
2. Highlights the most important developments
3. Shows how events connect to each other
4. Uses engaging storytelling language

NARRATIVE:"""
        
        messages = [
            {
                "role": "system",
                "content": "You are a chronicler writing historical narratives."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            narrative = chat_completion(messages, max_tokens=500, temperature=0.7)
            return narrative.strip()
        except Exception as e:
            logger.error(f"Timeline narrative failed: {e}")
            return "Unable to generate timeline narrative."
    
    def synthesize_relationship_explanation(
        self,
        connections_result: Dict
    ) -> str:
        """
        Explains the relationships an entity has.
        
        Args:
            connections_result: Dict from LoreRetriever.retrieve_connections()
            
        Returns:
            Relationship explanation
        """
        if not connections_result.get("found"):
            return connections_result.get("message", "Entity not found")
        
        entity = connections_result["entity"]
        connections = connections_result.get("connections", [])
        
        if not connections:
            return f"{entity['name']} has no recorded relationships."
        
        # Build connections text
        conn_text = []
        for conn in connections[:15]:
            target = conn.get("target", {})
            relation = conn.get("relation", "")
            desc = conn.get("description", "")
            
            conn_text.append(
                f"- {relation.replace('_', ' ')} {target.get('name', 'Unknown')} "
                f"({target.get('type', 'unknown')}): {desc}"
            )
        
        prompt = f"""Describe the relationships and connections of this entity.

ENTITY: {entity['name']} ({entity['type']})

CONNECTIONS:
{chr(10).join(conn_text)}

Write 1-2 paragraphs that:
1. Summarize the entity's key relationships
2. Group similar relationships together
3. Highlight the most important connections
4. Use natural, flowing language

DESCRIPTION:"""
        
        messages = [
            {
                "role": "system",
                "content": "You are describing the social and physical connections of entities in a world."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            explanation = chat_completion(messages, max_tokens=350, temperature=0.7)
            return explanation.strip()
        except Exception as e:
            logger.error(f"Relationship explanation failed: {e}")
            return f"Unable to explain relationships for {entity['name']}"
