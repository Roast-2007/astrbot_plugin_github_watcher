from __future__ import annotations

from astrbot.api.event import AstrMessageEvent


async def is_group_admin_or_owner(event: AstrMessageEvent) -> bool:
    if event.is_admin():
        return True
    group = await event.get_group()
    if group is None:
        return False
    sender_id = str(event.get_sender_id())
    owner = str(group.group_owner or "")
    admins = {str(admin_id) for admin_id in (group.group_admins or [])}
    return sender_id == owner or sender_id in admins
