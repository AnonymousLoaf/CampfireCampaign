"""Table chat: out-of-character messages between the people in a game (kept apart from the story log)."""
import os
import tempfile
import time

if "GAME_DATA_DIR" not in os.environ:
    os.environ["GAME_DATA_DIR"] = tempfile.mkdtemp(prefix="dndgame-chat-")
os.environ.setdefault("GAME_TICK_SECONDS", "0.2")

from fastapi.testclient import TestClient  # noqa: E402

from app.game import notify  # noqa: E402
from app.main import app  # noqa: E402


def _client(name):
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"username": name, "password": "secret123", "display_name": name.title()})
    assert r.status_code == 200, r.text
    return c


def _character(c, name):
    opts = c.get("/api/rules/creator?ruleset=2024").json()
    fighter = next(x for x in opts["classes"] if x["index"] == "fighter")
    bg = opts["backgrounds"][0]
    race = opts["races"][0]
    p = {"ruleset": "2024", "name": name, "race": race["index"], "class": "fighter", "background": bg["index"],
         "ability_method": "standard", "abilities": {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8},
         "skills": [s for s in fighter["skill_choices"]["options"] if s not in bg["skills"]][:2],
         "equipment_option": fighter["equipment_options"][0]["id"], "fighting_style": "Defense",
         "background_asi": {bg["ability_options"][0]: 2, bg["ability_options"][1]: 1}}
    if race["subraces"]:
        p["subrace"] = race["subraces"][0]["index"]
    r = c.post("/api/characters", json=p)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _game(prefix):
    host, player, watcher, outsider = (_client(f"{prefix}{n}") for n in ("host", "player", "watch", "out"))
    gid = host.post("/api/games", json={"name": "Chat test", "character_id": _character(host, "Ash"),
                                        "settings": {"ruleset": "2024"}}).json()["id"]
    code = host.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
    assert player.post("/api/games/join", json={"invite_code": code,
                                                "character_id": _character(player, "Bryn")}).status_code == 200
    assert watcher.post("/api/games/join", json={"invite_code": code, "spectate": True}).status_code == 200
    return gid, host, player, watcher, outsider


def test_chat_post_list_edit_delete_and_unread():
    with TestClient(app):
        gid, host, player, watcher, outsider = _game("chat1")
        r = host.post(f"/api/games/{gid}/chat", json={"text": "  Flank the ogre from the left?  "})
        assert r.status_code == 200, r.text
        m1 = r.json()
        assert m1["text"] == "Flank the ogre from the left?" and m1["author"] == "Chat1Host"
        m2 = player.post(f"/api/games/{gid}/chat", json={"text": "On it."}).json()

        # everyone in the game reads it, outsiders can't; spectators read but can't post
        msgs = watcher.get(f"/api/games/{gid}/chat").json()["messages"]
        assert [m["id"] for m in msgs] == [m1["id"], m2["id"]]
        assert outsider.get(f"/api/games/{gid}/chat").status_code == 403
        assert outsider.post(f"/api/games/{gid}/chat", json={"text": "hi"}).status_code == 403
        assert watcher.post(f"/api/games/{gid}/chat", json={"text": "boo"}).status_code == 403

        # validation
        assert host.post(f"/api/games/{gid}/chat", json={"text": "   "}).status_code == 400
        assert host.post(f"/api/games/{gid}/chat", json={"text": "x" * 1001}).status_code == 400

        # unread counts skip your own messages; posting marks the chat read for you
        assert host.get(f"/api/games/{gid}/view").json()["me"]["chat_unseen"] == 1
        assert player.get(f"/api/games/{gid}/view").json()["me"]["chat_unseen"] == 0
        assert watcher.get(f"/api/games/{gid}/view").json()["me"]["chat_unseen"] == 2
        assert host.post(f"/api/games/{gid}/chat/seen", json={"message_id": m2["id"]}).status_code == 200
        assert host.get(f"/api/games/{gid}/view").json()["me"]["chat_unseen"] == 0

        # edit your own; not someone else's
        assert player.patch(f"/api/games/{gid}/chat/{m1['id']}", json={"text": "nope"}).status_code == 403
        r = host.patch(f"/api/games/{gid}/chat/{m1['id']}", json={"text": "Flank right instead."})
        assert r.status_code == 200 and r.json()["edited"] and r.json()["text"] == "Flank right instead."

        # delete your own; the host can remove anyone's; a placeholder remains
        assert player.delete(f"/api/games/{gid}/chat/{m1['id']}").status_code == 403
        assert host.delete(f"/api/games/{gid}/chat/{m2['id']}").status_code == 200
        msgs = host.get(f"/api/games/{gid}/chat").json()["messages"]
        gone = next(m for m in msgs if m["id"] == m2["id"])
        assert gone["deleted"] and gone["text"] == ""
        assert host.patch(f"/api/games/{gid}/chat/{m2['id']}", json={"text": "back"}).status_code == 404

        # chat never reaches the story log (so the DM never reads it)
        log = host.get(f"/api/games/{gid}/log?limit=200").json()["entries"]
        assert not any("Flank" in (e["text"] or "") for e in log)


def test_chat_paging():
    with TestClient(app):
        gid, host, *_ = _game("chat2")
        ids = [host.post(f"/api/games/{gid}/chat", json={"text": f"msg {i}"}).json()["id"] for i in range(7)]
        page = host.get(f"/api/games/{gid}/chat?limit=3").json()
        assert [m["id"] for m in page["messages"]] == ids[-3:] and page["has_more"]
        older = host.get(f"/api/games/{gid}/chat?limit=3&before_id={ids[-3]}").json()
        assert [m["id"] for m in older["messages"]] == ids[-6:-3]


def test_chat_websocket_and_leaving():
    with TestClient(app):
        gid, host, player, watcher, _ = _game("chat3")
        with player.websocket_connect("/api/ws") as ws:
            ws.send_json({"subscribe": gid})
            time.sleep(0.2)
            m = host.post(f"/api/games/{gid}/chat", json={"text": "Ready?"}).json()
            msg = ws.receive_json()
            while msg.get("type") != "chat":
                msg = ws.receive_json()
            assert msg["game_id"] == gid and msg["message"]["id"] == m["id"] and msg["message"]["text"] == "Ready?"

        # a TV link sees the game but never the chat
        tv = host.post(f"/api/games/{gid}/tv-link").json()
        token = (tv.get("url") or tv.get("tv_url") or "").rstrip("/").split("/")[-1]
        if token:
            anon = TestClient(app)
            with anon.websocket_connect("/api/ws") as ws:
                ws.send_json({"subscribe_tv": token})
                time.sleep(0.2)
                from app.game.hub import hub
                assert not any(gid in c.member_games for c in hub.conns if c.user_id is None)

        # after leaving, the chat is closed to them
        assert watcher.post(f"/api/games/{gid}/leave").status_code == 200
        assert watcher.get(f"/api/games/{gid}/chat").status_code == 403


def test_chat_push_is_opt_in_and_rate_limited(monkeypatch):
    sent = []

    async def fake_notify_users(user_ids, title, body, url="/", email=True):
        sent.append((list(user_ids), title, body, email))

    monkeypatch.setattr(notify, "notify_users", fake_notify_users)
    with TestClient(app):
        gid, host, player, watcher, _ = _game("chat4")
        me = player.get("/api/me").json()
        assert me["notify"]["chat"] is False  # off by default
        host.post(f"/api/games/{gid}/chat", json={"text": "anyone there?"})
        time.sleep(0.3)
        assert sent == []

        r = player.put("/api/me/notifications", json={"notify_chat": True})
        assert r.status_code == 200 and r.json()["notify"]["chat"] is True
        host.post(f"/api/games/{gid}/chat", json={"text": "We fight at dawn."})
        time.sleep(0.3)
        assert len(sent) == 1
        users, title, body, email = sent[0]
        assert users == [player.get("/api/me").json()["id"]] and "Chat4Host" in title
        assert body == "We fight at dawn." and email is False

        host.post(f"/api/games/{gid}/chat", json={"text": "And bring rope."})
        time.sleep(0.3)
        assert len(sent) == 1  # at most one push per 10 minutes per game

        # nothing while the player has the game open
        notify._chat_pushed.clear()
        with player.websocket_connect("/api/ws") as ws:
            ws.send_json({"subscribe": gid})
            time.sleep(0.2)
            host.post(f"/api/games/{gid}/chat", json={"text": "You there?"})
            time.sleep(0.3)
        assert len(sent) == 1
