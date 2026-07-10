from uuid import uuid4
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from typing import List, Dict, Any
from engine import GameEngine
from ai_service import AIService

app = FastAPI(title="Old Maid AI Server")
ai_service = AIService()

# Global in-memory storage for active games (use Redis/Database for production scale)
ACTIVE_GAMES: Dict[str, GameEngine] = {}

class CreateGameRequest(BaseModel):
    house_rules: str

class JoinGameRequest(BaseModel):
    player_name: str
    player_type: str = "human"  # or "ai"

class HumanMoveRequest(BaseModel):
    card_index: int

@app.post("/game/create")
async def create_game(req: CreateGameRequest):
    engine = GameEngine(house_rules=req.house_rules)
    game_id = uuid4().hex
    ACTIVE_GAMES[game_id] = engine
    
    return {"status": "Game created", "game_id": game_id}

@app.post("/game/{game_id}/join_game")
async def join_game(game_id: str, req: JoinGameRequest):
    if game_id not in ACTIVE_GAMES:
        raise HTTPException(status_code=404, detail="Game not found.")
    
    engine = ACTIVE_GAMES[game_id]
    if req.player_name in engine.players:
        raise HTTPException(status_code=400, detail="Player name already taken.")
    
    engine.add_player(req.player_name, player_type=req.player_type)
        
    return {"status": f"{req.player_name} joined the game."}

@app.post("/game/{game_id}/start")
async def start_game(game_id: str):
    if game_id not in ACTIVE_GAMES:
        raise HTTPException(status_code=404, detail="Game not found.")
    
    engine = ACTIVE_GAMES[game_id]
    if len(engine.players) < 2:
        engine.add_player("AI_Opponent", player_type="ai")  # Add an AI opponent if only one human player
    
    engine._initialize_game()
    
    return {
        "status": "Game started",
        "player_hands": {p: [c.to_dict() for c in player.hand] for p, player in engine.players.items()},
        "current_turn": list(engine.players.keys())[engine.current_turn_index]
    }

@app.get("/game/{game_id}/state/{player_name}")
async def get_player_state(game_id: str, player_name: str):
    """Returns game state tailored exclusively to what a specific player is allowed to see."""
    if game_id not in ACTIVE_GAMES:
        raise HTTPException(status_code=404, detail="Game not found.")
    
    engine = ACTIVE_GAMES[game_id]
    if player_name not in engine.players:
        raise HTTPException(status_code=404, detail="Player not in this game.")

    # Hide actual card structures of opponents; only provide counts
    opponent_hand_counts = {}
    for p, player in engine.players.items():
        if p != player_name:
            opponent_hand_counts[p] = len(player.hand)

    return {
        "your_hand": [card.to_dict() for card in engine.players[player_name].hand],
        "opponents_card_counts": opponent_hand_counts,
        "current_turn": list(engine.players.keys())[engine.current_turn_index]
    }

@app.post("/game/{game_id}/move/human")
async def human_move(game_id: str, player_name: str, move: HumanMoveRequest):
    engine = ACTIVE_GAMES[game_id]
    current_turn_player = list(engine.players.keys())[engine.current_turn_index]
    
    if current_turn_player != player_name:
        raise HTTPException(status_code=400, detail="It is not your turn.")

    target_player = engine.get_next_player(player_name)
    try:
        result = engine.execute_draw(player_name, target_player, move.card_index)
        return {
            "status": "success",
            "action": f"You drew a card from {target_player}",
            "details": result,
            "next_turn": list(engine.players.keys())[engine.current_turn_index],
            "verdict": "You drew a card successfully." if len(engine.players) > 1 else "Game over, you are the last player remaining."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/game/{game_id}/move/ai")
async def ai_move(game_id: str, ai_player_name: str):
    engine = ACTIVE_GAMES[game_id]
    current_turn_player = list(engine.players.keys())[engine.current_turn_index]
    
    if current_turn_player != ai_player_name:
        raise HTTPException(status_code=400, detail="It is not the AI's turn.")
    
    target_player = engine.get_next_player(ai_player_name)
    target_card_count = len(engine.players[target_player].hand)
    
    # Format AI hand cleanly for prompt context
    ai_hand_serialized = [f"{c.rank} of {c.suit} ({c.color})" for c in engine.players[ai_player_name].hand]
    
    # Ask the LLM to make a structured move decision
    ai_decision = await ai_service.get_ai_move(
        ai_hand=ai_hand_serialized,
        target_card_count=target_card_count,
        house_rules=engine.house_rules
    )
    
    # Execute the move the AI requested
    result = engine.execute_draw(ai_player_name, target_player, ai_decision.chosen_index)
    
    return {
        "status": "success",
        "ai_player": ai_player_name,
        "target_drawn_from": target_player,
        "ai_commentary": ai_decision.roleplay_comment,
        "new_pairs_discarded_by_ai": result["new_pairs_formed"],
        "next_turn": list(engine.players.keys())[engine.current_turn_index],
        "verdict": "AI drew a card successfully." if len(engine.players) > 1 else "Game over, AI is the last player remaining."
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)