from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI(title="Random Draw Room API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Моделі ----

class Participant(BaseModel):
    id: str
    name: str

class RoomState(BaseModel):
    room_id: str
    participants: List[Participant]
    is_draw_done: bool = False
    winner_id: Optional[str] = None

class AddParticipantRequest(BaseModel):
    name: str

class DrawResponse(BaseModel):
    room_id: str
    winner: Participant

# ---- In-memory “БД” ----

ROOMS: Dict[str, RoomState] = {
    "r1": RoomState(
        room_id="r1",
        participants=[
            Participant(id="u1", name="Illia"),
            Participant(id="u2", name="Denis"),
            Participant(id="u3", name="Victoria"),
            Participant(id="u4", name="Emile"),
            Participant(id="u5", name="Spenser"),
            Participant(id="u6", name="Phil"),
        ],
        is_draw_done=False,
        winner_id=None,
    )
}

# ---- Ендпоінти ----

@app.get("/rooms/{room_id}", response_model=RoomState)
def get_room(room_id: str):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ROOM_NOT_FOUND")
    return room

@app.post("/rooms/{room_id}/participants", response_model=RoomState)
def add_participant(room_id: str, body: AddParticipantRequest):
    room = ROOMS.get(room_id)
    if not room:
        # cтворюємо кімнату на льоту, якщо треба
        room = RoomState(room_id=room_id, participants=[])
        ROOMS[room_id] = room

    if room.is_draw_done:
        raise HTTPException(status_code=409, detail="DRAW_ALREADY_DONE")

    new_id = f"u{len(room.participants) + 1}"
    room.participants.append(Participant(id=new_id, name=body.name))
    return room

@app.post("/rooms/{room_id}/draw", response_model=DrawResponse)
def start_draw(room_id: str):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ROOM_NOT_FOUND")

    # Якщо вже тягнули — завжди повертаємо існуючого переможця (200)
    if room.is_draw_done:
        if room.winner_id:
            winner = next((p for p in room.participants if p.id == room.winner_id), None)
            if winner:
                return DrawResponse(room_id=room_id, winner=winner)
            # Фолбек: якщо winner_id зламався — перевизначаємо переможця, щоб не падати з 409
            if room.participants:
                winner = random.choice(room.participants)
                room.winner_id = winner.id
                return DrawResponse(room_id=room_id, winner=winner)
        # Якщо сюди дійшли — значить щось зовсім не так зі станом; але краще не 409
        if not room.participants:
            raise HTTPException(status_code=400, detail="NO_PARTICIPANTS")
        winner = random.choice(room.participants)
        room.winner_id = winner.id
        return DrawResponse(room_id=room_id, winner=winner)

    # Нормальний перший розіграш
    if not room.participants:
        raise HTTPException(status_code=400, detail="NO_PARTICIPANTS")

    winner = random.choice(room.participants)
    room.is_draw_done = True
    room.winner_id = winner.id
    return DrawResponse(room_id=room_id, winner=winner)


@app.post("/rooms/{room_id}/reset_draw", response_model=RoomState)
def reset_draw(room_id: str):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ROOM_NOT_FOUND")
    room.is_draw_done = False
    room.winner_id = None
    return room

@app.delete("/rooms/{room_id}/participants/{participant_id}", response_model=RoomState)
def remove_participant(room_id: str, participant_id: str):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ROOM_NOT_FOUND")
    if room.is_draw_done:
        raise HTTPException(status_code=409, detail="DRAW_ALREADY_DONE")

    before = len(room.participants)
    room.participants = [p for p in room.participants if p.id != participant_id]
    if len(room.participants) == before:
        raise HTTPException(status_code=404, detail="PARTICIPANT_NOT_FOUND")

    # про всяк випадок: якщо видалили переможця до оголошення - скинемо
    if room.winner_id == participant_id:
        room.winner_id = None
        room.is_draw_done = False
    return room