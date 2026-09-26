import discord
from discord.ext import commands
import json
import os
import asyncio

# ====================== НАСТРОЙКИ ======================
TOKEN = "MTU1MzM5NjcwNTcyOTE5MjA4Ng.GTC_Ox.zx9P7el2GPo8fWo4njD-GN4lvq8j7eYK0VCxmg"  # ← не трогай

# Канал, куда приходят заявки
LOG_CHANNEL_ID = 1530613645640470680

# 5 голосовых каналов для обзвона
VOICE_CHANNELS = {
    "Войс 1": 1530614579992723747,
    "Войс 2": 1530614582966751292,
    "Войс 3": 1530614586032787587,
    "Войс 4": 1530614590218440886,
    "Войс 5": 1530614593305575577,
}

# ========== ВРЕМЕННЫЕ ВОЙСЫ ==========
CREATE_VOICE_ID = 1530614600674840667       # ID голосового канала «Создание»
CONTROL_CHANNEL_ID = 1530613738070081799    # ID текстового канала «управление»
# =====================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# channel_id -> owner_id
temp_channels: dict[int, int] = {}

# ==========================================
# НУМЕРАЦИЯ ЗАЯВОК
# ==========================================
COUNTER_FILE = "app_counter.json"

def get_next_app_number() -> int:
    if not os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "w", encoding="utf-8") as f:
            json.dump({"last": 0}, f)
    
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    data["last"] += 1
    
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    
    return data["last"]

# ==========================================
# ФОРМА 1: ACADEMY
# ==========================================
class AcademyModal(discord.ui.Modal, title="Заявка: роль ACADEMY"):
    nickname = discord.ui.TextInput(
        label="Ник в игре | Имя и возраст",
        placeholder="Пример: Sotori Karnage | Иван 19",
        required=True,
        max_length=100
    )
    playtime = discord.ui.TextInput(
        label="Как давно играете на проекте?",
        placeholder="Пример: с апреля 2021 года",
        required=True,
        max_length=100
    )
    timezone = discord.ui.TextInput(
        label="Часовой пояс + среднесуточный онлайн.",
        placeholder="Пример: +3 от мск, 5-6 часов в день",
        required=True,
        max_length=100
    )
    families = discord.ui.TextInput(
        label="Назовите ВСЕ ваши предыдущие семьи",
        placeholder="Пример: причина ухода. Haunted – дизбанд, Movavi – кинкули и т.д.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    clips = discord.ui.TextInput(
        label="Предоставьте свои откаты",
        placeholder="Для Academy откаты не требуются — можно оставить пустым",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application(
            interaction, "ACADEMY",
            self.nickname.value, self.playtime.value,
            self.timezone.value, self.families.value, self.clips.value
        )

# ==========================================
# ФОРМА 2: TEST
# ==========================================
class TestModal(discord.ui.Modal, title="Заявка: роль TEST"):
    nickname = discord.ui.TextInput(
        label="Ник в игре | Имя и возраст",
        placeholder="Пример: Sotori Karnage | Иван 19",
        required=True,
        max_length=100
    )
    playtime = discord.ui.TextInput(
        label="Как давно играете на проекте?",
        placeholder="Пример: с апреля 2021 года",
        required=True,
        max_length=100
    )
    timezone = discord.ui.TextInput(
        label="Часовой пояс + среднесуточный онлайн.",
        placeholder="Пример: +3 от мск, 5-6 часов в день",
        required=True,
        max_length=100
    )
    families = discord.ui.TextInput(
        label="Назовите ВСЕ ваши предыдущие семьи",
        placeholder="Пример: причина ухода. Haunted – дизбанд, Movavi – кинкули и т.д.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    clips = discord.ui.TextInput(
        label="Предоставьте свои откаты",
        placeholder="Тяжка/Сайга от 5 мин, полных 4-5 с MCL/Capt + GunGame (обязательно)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application(
            interaction, "TEST",
            self.nickname.value, self.playtime.value,
            self.timezone.value, self.families.value, self.clips.value
        )

# ==========================================
# КНОПКИ ДЛЯ ЗАЯВКИ
# ==========================================
class ApplicationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ У вас нет прав для работы с заявками.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, emoji="✅", custom_id="app_accept")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_decision(interaction, accepted=True)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, emoji="❌", custom_id="app_decline")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_decision(interaction, accepted=False)

    @discord.ui.button(label="Вызвать на обзвон", style=discord.ButtonStyle.secondary, emoji="📞", custom_id="app_call")
    async def call_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            footer = interaction.message.embeds[0].footer.text
            parts = footer.split(" • ")
            applicant_id = int(parts[0].replace("ID пользователя: ", ""))
            app_number = parts[2].replace("app#", "")
            role_type = parts[3]
        except Exception:
            await interaction.response.send_message("❌ Не удалось прочитать данные заявки.", ephemeral=True)
            return

        applicant = interaction.guild.get_member(applicant_id)
        if not applicant:
            await interaction.response.send_message("Пользователь не найден на сервере.", ephemeral=True)
            return

        view = VoiceSelectView(
            applicant_id=applicant_id,
            applicant_mention=applicant.mention,
            app_number=app_number,
            role_type=role_type,
            recruiter=interaction.user
        )
        await interaction.response.send_message(
            f"📞 Выберите голосовой канал для обзвона **{applicant.display_name}**:",
            view=view,
            ephemeral=True
        )

    async def _handle_decision(self, interaction: discord.Interaction, accepted: bool):
        try:
            footer = interaction.message.embeds[0].footer.text
            parts = footer.split(" • ")
            applicant_id = int(parts[0].replace("ID пользователя: ", ""))
            app_number = parts[2].replace("app#", "")
            role_type = parts[3]
        except Exception:
            await interaction.response.send_message("❌ Не удалось прочитать данные заявки.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True

        status = "✅ **ПРИНЯТА**" if accepted else "❌ **ОТКЛОНЕНА**"
        color = discord.Color.green() if accepted else discord.Color.red()

        embed = interaction.message.embeds[0]
        embed.color = color
        embed.add_field(name="Статус", value=f"{status}\nРешение принял: {interaction.user.mention}", inline=False)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f"Заявка #{app_number} {status.lower()} пользователем {interaction.user.mention}",
            ephemeral=True
        )

        applicant = interaction.guild.get_member(applicant_id)
        if applicant:
            try:
                if accepted:
                    await applicant.send(
                        f"✅ Ваша заявка **#{app_number}** на роль **{role_type}** была **принята**!\n"
                        f"Ожидайте дальнейших инструкций от рекрута."
                    )
                else:
                    await applicant.send(
                        f"❌ Ваша заявка **#{app_number}** на роль **{role_type}** была **отклонена**.\n"
                        f"Вы можете подать новую заявку через 1 день (КД)."
                    )
            except discord.Forbidden:
                pass

# ==========================================
# ВЫБОР ГОЛОСОВОГО КАНАЛА
# ==========================================
class VoiceSelectView(discord.ui.View):
    def __init__(self, applicant_id: int, applicant_mention: str, app_number: str, role_type: str, recruiter: discord.Member):
        super().__init__(timeout=60)
        self.applicant_id = applicant_id
        self.applicant_mention = applicant_mention
        self.app_number = app_number
        self.role_type = role_type
        self.recruiter = recruiter

        options = [
            discord.SelectOption(label=name, value=str(channel_id), emoji="🔊")
            for name, channel_id in VOICE_CHANNELS.items()
        ]

        select = discord.ui.Select(placeholder="Выберите голосовой канал...", options=options, min_values=1, max_values=1)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_channel_id = int(interaction.data["values"][0])
        voice_channel = interaction.guild.get_channel(selected_channel_id)

        if not voice_channel:
            await interaction.response.send_message("❌ Голосовой канал не найден.", ephemeral=True)
            return

        applicant = interaction.guild.get_member(self.applicant_id)
        if not applicant:
            await interaction.response.send_message("❌ Пользователь больше не на сервере.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"✅ Вы вызвали {self.applicant_mention} в **{voice_channel.name}**",
            view=None
        )

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"📞 {self.applicant_mention} вызван на обзвон рекрутом {self.recruiter.mention}\n"
                f"Голосовой канал: {voice_channel.mention}"
            )

        dm_text = (
            f"✅ **Тебя вызвали на проверку.**\n"
            f"Финальный этап — обзвон.\n\n"
            f"🔊 **Перейди в голосовой канал:**\n"
            f"{voice_channel.mention}\n\n"
            f"Рекрут: **{self.recruiter.display_name}**\n\n"
            f"🕐 Вызывают в дневное время, иногда — в ночное.\n"
            f"⚠️ Не нужно писать в ЛС всем подряд и просить рассмотреть заявку — "
            f"это не ускорит процесс и может привести к отклонению заявки.\n\n"
            f"⏳ Срок — **2 суток**; при игнорировании заявка будет отклонена автоматически."
        )

        try:
            await applicant.send(dm_text)
        except discord.Forbidden:
            await interaction.followup.send(
                f"⚠️ Не удалось отправить ЛС {applicant.mention}.",
                ephemeral=True
            )

# ==========================================
# ОТПРАВКА ЗАЯВКИ
# ==========================================
async def send_application(interaction, role_type, nickname, playtime, timezone, families, clips):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    
    if not log_channel:
        await interaction.response.send_message("❌ Канал для заявок не найден.", ephemeral=True)
        return

    app_number = get_next_app_number()
    applicant = interaction.user

    header = f"**@Rec** — новая заявка на роль **{role_type}**. Просмотрите и, если всё устраивает — вызовите на обзвон."

    embed = discord.Embed(
        title=f"Заявка от пользователя {applicant.name} на роль {role_type}",
        color=discord.Color.dark_grey()
    )
    
    embed.add_field(name="Заявка", value=f"**#{app_number}**", inline=False)
    embed.add_field(name="Заявитель", value=applicant.mention, inline=False)
    embed.add_field(name="Ник в игре | Имя и возраст", value=nickname or "—", inline=False)
    embed.add_field(name="Как давно играете на проекте?", value=playtime or "—", inline=False)
    embed.add_field(name="Часовой пояс + среднесуточный онлайн.", value=timezone or "—", inline=False)
    embed.add_field(name="Назовите ВСЕ ваши предыдущие семьи", value=families or "—", inline=False)
    embed.add_field(name="Предоставьте свои откаты", value=clips if clips else "—", inline=False)
    
    embed.set_footer(text=f"ID пользователя: {applicant.id} • {applicant.name} • app#{app_number} • {role_type}")
    embed.timestamp = discord.utils.utcnow()

    view = ApplicationView()
    await log_channel.send(content=header, embed=embed, view=view)

    await interaction.response.send_message(
        "✅ Ваша заявка успешно отправлена! Ожидайте решения в личных сообщениях (в течение 1-3 рабочих дней).",
        ephemeral=True
    )

# ==========================================
# ВЫПАДАЮЩИЙ СПИСОК ЗАЯВОК
# ==========================================
class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Выберите тип заявки...",
        custom_id="application_select_menu",
        options=[
            discord.SelectOption(label="Academy", description="Для новичков — откаты не требуются", value="academy", emoji="📚"),
            discord.SelectOption(label="Test", description="Предварительный отбор — полные откаты", value="test", emoji="⚔️")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "academy":
            await interaction.response.send_modal(AcademyModal())
        elif select.values[0] == "test":
            await interaction.response.send_modal(TestModal())

# ============================================================
# ==================== ВРЕМЕННЫЕ ВОЙСЫ =======================
# ============================================================

class TempControlView(discord.ui.View):
    """Статичная панель управления — всегда одна"""
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ Кнопки становятся активными, когда Вы находитесь в своём приватном канале.",
                ephemeral=True
            )
            return False

        channel = interaction.user.voice.channel
        owner_id = temp_channels.get(channel.id)

        if owner_id is None:
            await interaction.response.send_message(
                "❌ Вы находитесь не в приватной комнате.",
                ephemeral=True
            )
            return False

        if interaction.user.id != owner_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Только владелец комнаты может управлять ею.",
                ephemeral=True
            )
            return False

        return True

    async def get_user_channel(self, interaction: discord.Interaction) -> discord.VoiceChannel | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            return None
        return interaction.user.voice.channel

    # ==================== РЯД 1 ====================
    @discord.ui.button(emoji="➕", style=discord.ButtonStyle.secondary, row=0, custom_id="temp_add_slot")
    async def add_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.get_user_channel(interaction)
        if not channel:
            return
        new_limit = min(99, (channel.user_limit or 0) + 1)
        await channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"✅ Добавлен слот. Лимит: **{new_limit}**", ephemeral=True)

    @discord.ui.button(emoji="➖", style=discord.ButtonStyle.secondary, row=0, custom_id="temp_rem_slot")
    async def rem_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.get_user_channel(interaction)
        if not channel:
            return
        new_limit = max(0, (channel.user_limit or 0) - 1)
        await channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"✅ Убран слот. Лимит: **{new_limit if new_limit else 'безлимит'}**", ephemeral=True)

    @discord.ui.button(emoji="👥", style=discord.ButtonStyle.secondary, row=0, custom_id="temp_set_limit")
    async def set_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        class LimitModal(discord.ui.Modal, title="Изменить слоты"):
            limit = discord.ui.TextInput(label="Количество слотов (0 = безлимит)", max_length=2, required=True)
            async def on_submit(modal_self, inter: discord.Interaction):
                try:
                    val = int(modal_self.limit.value)
                    if not 0 <= val <= 99:
                        raise ValueError
                except:
                    await inter.response.send_message("❌ Введите число от 0 до 99.", ephemeral=True)
                    return
                ch = inter.user.voice.channel if inter.user.voice else None
                if ch:
                    await ch.edit(user_limit=val)
                    await inter.response.send_message(f"✅ Лимит слотов: **{val if val else 'безлимит'}**", ephemeral=True)
                else:
                    await inter.response.send_message("❌ Вы не в голосовом канале.", ephemeral=True)
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(emoji="🔓", style=discord.ButtonStyle.secondary, row=0, custom_id="temp_unlock")
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.get_user_channel(interaction)
        if not channel:
            return
        await channel.set_permissions(interaction.guild.default_role, connect=True)
        await interaction.response.send_message("🔓 Канал **открыт**.", ephemeral=True)

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.secondary, row=0, custom_id="temp_lock")
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.get_user_channel(interaction)
        if not channel:
            return
        await channel.set_permissions(interaction.guild.default_role, connect=False)
        await interaction.response.send_message("🔒 Канал **закрыт**.", ephemeral=True)

    # ==================== РЯД 2 ====================
    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.secondary, row=1, custom_id="temp_add_user")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        class AddUserModal(discord.ui.Modal, title="Добавить пользователя"):
            user_id = discord.ui.TextInput(label="ID или упоминание пользователя", required=True)
            async def on_submit(modal_self, inter: discord.Interaction):
                ch = inter.user.voice.channel if inter.user.voice else None
                if not ch:
                    await inter.response.send_message("❌ Вы не в голосовом канале.", ephemeral=True)
                    return
                raw = modal_self.user_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
                try:
                    uid = int(raw)
                except:
                    await inter.response.send_message("❌ Неверный ID.", ephemeral=True)
                    return
                member = inter.guild.get_member(uid)
                if not member:
                    await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
                    return
                await ch.set_permissions(member, connect=True, speak=True, view_channel=True)
                await inter.response.send_message(f"✅ {member.mention} добавлен в канал.", ephemeral=True)
        await interaction.response.send_modal(AddUserModal())

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.secondary, row=1, custom_id="temp_rem_user")
    async def rem_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        class RemUserModal(discord.ui.Modal, title="Убрать пользователя"):
            user_id = discord.ui.TextInput(label="ID или упоминание пользователя", required=True)
            async def on_submit(modal_self, inter: discord.Interaction):
                ch = inter.user.voice.channel if inter.user.voice else None
                if not ch:
                    await inter.response.send_message("❌ Вы не в голосовом канале.", ephemeral=True)
                    return
                raw = modal_self.user_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
                try:
                    uid = int(raw)
                except:
                    await inter.response.send_message("❌ Неверный ID.", ephemeral=True)
                    return
                member = inter.guild.get_member(uid)
                if not member:
                    await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
                    return
                await ch.set_permissions(member, connect=False)
                if member.voice and member.voice.channel and member.voice.channel.id == ch.id:
                    await member.move_to(None)
                await inter.response.send_message(f"✅ {member.mention} убран из канала.", ephemeral=True)
        await interaction.response.send_modal(RemUserModal())

    @discord.ui.button(emoji="👑", style=discord.ButtonStyle.secondary, row=1, custom_id="temp_transfer")
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        class TransferModal(discord.ui.Modal, title="Передать канал"):
            user_id = discord.ui.TextInput(label="ID или упоминание нового владельца", required=True)
            async def on_submit(modal_self, inter: discord.Interaction):
                ch = inter.user.voice.channel if inter.user.voice else None
                if not ch:
                    await inter.response.send_message("❌ Вы не в голосовом канале.", ephemeral=True)
                    return
                raw = modal_self.user_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
                try:
                    uid = int(raw)
                except:
                    await inter.response.send_message("❌ Неверный ID.", ephemeral=True)
                    return
                member = inter.guild.get_member(uid)
                if not member:
                    await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
                    return
                await ch.set_permissions(inter.user, overwrite=None)
                await ch.set_permissions(member, manage_channels=True, connect=True, speak=True, move_members=True, mute_members=True)
                temp_channels[ch.id] = member.id
                await inter.response.send_message(f"👑 Канал передан {member.mention}.", ephemeral=True)
        await interaction.response.send_modal(TransferModal())

    @discord.ui.button(emoji="🙈", style=discord.ButtonStyle.secondary, row=1, custom_id="temp_hide")
    async def hide(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.get_user_channel(interaction)
        if not channel:
            return
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message("🙈 Канал **скрыт**.", ephemeral=True)

    @discord.ui.button(emoji="👁️", style=discord.ButtonStyle.secondary, row=1, custom_id="temp_show")
    async def show(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.get_user_channel(interaction)
        if not channel:
            return
        await channel.set_permissions(interaction.guild.default_role, view_channel=True)
        await interaction.response.send_message("👁️ Канал **показан**.", ephemeral=True)

    # ==================== РЯД 3 ====================
    @discord.ui.button(emoji="✏️", style=discord.ButtonStyle.secondary, row=2, custom_id="temp_rename")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        class RenameModal(discord.ui.Modal, title="Переименовать канал"):
            name = discord.ui.TextInput(label="Новое название", max_length=100, required=True)
            async def on_submit(modal_self, inter: discord.Interaction):
                ch = inter.user.voice.channel if inter.user.voice else None
                if ch:
                    await ch.edit(name=modal_self.name.value)
                    await inter.response.send_message(f"✅ Канал переименован в **{modal_self.name.value}**", ephemeral=True)
                else:
                    await inter.response.send_message("❌ Вы не в голосовом канале.", ephemeral=True)
        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(emoji="🚫", style=discord.ButtonStyle.secondary, row=2, custom_id="temp_block")
    async def block_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        class BlockModal(discord.ui.Modal, title="Заблокировать пользователя"):
            user_id = discord.ui.TextInput(label="ID или упоминание пользователя", required=True)
            async def on_submit(modal_self, inter: discord.Interaction):
                ch = inter.user.voice.channel if inter.user.voice else None
                if not ch:
                    await inter.response.send_message("❌ Вы не в голосовом канале.", ephemeral=True)
                    return
                raw = modal_self.user_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
                try:
                    uid = int(raw)
                except:
                    await inter.response.send_message("❌ Неверный ID.", ephemeral=True)
                    return
                member = inter.guild.get_member(uid)
                if not member:
                    await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
                    return
                await ch.set_permissions(member, connect=False, view_channel=False)
                if member.voice and member.voice.channel and member.voice.channel.id == ch.id:
                    await member.move_to(None)
                await inter.response.send_message(f"🚫 {member.mention} заблокирован.", ephemeral=True)
        await interaction.response.send_modal(BlockModal())

async def create_temp_voice(member: discord.Member, create_channel: discord.VoiceChannel):
    guild = member.guild
    category = create_channel.category

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
        member: discord.PermissionOverwrite(
            manage_channels=True,
            connect=True,
            speak=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
            view_channel=True
        ),
        guild.me: discord.PermissionOverwrite(
            connect=True,
            manage_channels=True,
            move_members=True,
            view_channel=True
        )
    }

    name = f"🔊 {member.display_name}"
    
    try:
        new_channel = await guild.create_voice_channel(
            name=name,
            category=category,
            overwrites=overwrites,
            reason=f"Временная комната для {member}"
        )
        print(f"[TEMP] Создан канал {new_channel.name} для {member}")
    except Exception as e:
        print(f"[TEMP] Ошибка создания канала: {e}")
        return

    try:
        await member.move_to(new_channel)
    except Exception as e:
        print(f"[TEMP] Не удалось переместить: {e}")
        try:
            await new_channel.delete()
        except:
            pass
        return

    temp_channels[new_channel.id] = member.id

async def cleanup_temp_channel(channel: discord.VoiceChannel):
    if channel.id not in temp_channels:
        return
    if len(channel.members) == 0:
        try:
            await channel.delete(reason="Временная комната опустела")
            print(f"[TEMP] Удалён пустой канал {channel.name}")
        except Exception as e:
            print(f"[TEMP] Ошибка удаления канала: {e}")
        temp_channels.pop(channel.id, None)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # Создание временного войса
    if after.channel and after.channel.id == CREATE_VOICE_ID:
        await asyncio.sleep(0.4)
        if member.voice and member.voice.channel and member.voice.channel.id == CREATE_VOICE_ID:
            await create_temp_voice(member, after.channel)

    # Удаление пустых временных
    if before.channel and before.channel.id in temp_channels:
        await asyncio.sleep(1.2)
        channel = bot.get_channel(before.channel.id)
        if channel and isinstance(channel, discord.VoiceChannel):
            await cleanup_temp_channel(channel)

# ==========================================
# ЗАПУСК И КОМАНДЫ
# ==========================================
@bot.event
async def on_ready():
    print(f"Бот {bot.user} успешно запущен и готов к работе!")
    
    bot.add_view(ApplyView())
    bot.add_view(ApplicationView())
    bot.add_view(TempControlView())

    # Очистка пустых временных при старте
    for channel_id in list(temp_channels.keys()):
        ch = bot.get_channel(channel_id)
        if ch and isinstance(ch, discord.VoiceChannel) and len(ch.members) == 0:
            try:
                await ch.delete()
                temp_channels.pop(channel_id, None)
            except:
                pass

    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(e)

@bot.command(name="setup_temp_panel")
@commands.has_permissions(administrator=True)
async def setup_temp_panel(ctx):
    """Устанавливает статичную панель управления временными войсами"""
    try:
        await ctx.message.delete()
    except:
        pass

    print(f"[SETUP] Запущена установка панели. CONTROL_CHANNEL_ID = {CONTROL_CHANNEL_ID}")

    control_channel = bot.get_channel(CONTROL_CHANNEL_ID)
    
    if control_channel is None:
        error_msg = f"❌ Канал с ID `{CONTROL_CHANNEL_ID}` не найден.\nПроверь, правильно ли указан CONTROL_CHANNEL_ID."
        print(f"[SETUP] {error_msg}")
        await ctx.send(error_msg, delete_after=15)
        return

    print(f"[SETUP] Канал найден: {control_channel.name} ({control_channel.id})")

    perms = control_channel.permissions_for(ctx.guild.me)
    if not perms.send_messages:
        error_msg = f"❌ У бота нет права **Отправлять сообщения** в канале {control_channel.mention}"
        print(f"[SETUP] {error_msg}")
        await ctx.send(error_msg, delete_after=15)
        return
    if not perms.embed_links:
        error_msg = f"❌ У бота нет права **Встраивать ссылки** в канале {control_channel.mention}"
        print(f"[SETUP] {error_msg}")
        await ctx.send(error_msg, delete_after=15)
        return

    embed = discord.Embed(
        title="Управление приватной комнатой",
        description=(
            "➕ • Добавить слот\n"
            "➖ • Убрать слот\n"
            "👥 • Изменить слоты\n"
            "👑 • Передать канал\n"
            "🔓 • Открыть канал\n"
            "🔒 • Закрыть канал\n"
            "✅ • Добавить пользователя\n"
            "❌ • Убрать пользователя\n"
            "🙈 • Скрыть канал\n"
            "👁️ • Показать канал\n"
            "✏️ • Переименовать канал\n"
            "🚫 • Заблокировать пользователя\n\n"
            "Кнопки становятся активными, когда Вы находитесь в своём приватном канале."
        ),
        color=discord.Color.dark_grey()
    )

    view = TempControlView()

    try:
        msg = await control_channel.send(embed=embed, view=view)
        print(f"[SETUP] Панель успешно отправлена! Message ID: {msg.id}")
        await ctx.send(f"✅ Панель успешно установлена в {control_channel.mention}", delete_after=8)
    except discord.Forbidden:
        error_msg = f"❌ Нет прав на отправку сообщения в {control_channel.mention}"
        print(f"[SETUP] {error_msg}")
        await ctx.send(error_msg, delete_after=15)
    except Exception as e:
        error_msg = f"❌ Ошибка при отправке панели: `{type(e).__name__}: {e}`"
        print(f"[SETUP] {error_msg}")
        await ctx.send(error_msg, delete_after=15)

@bot.command(name="setup_karnage")
@commands.has_permissions(administrator=True)
async def setup_karnage(ctx):
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="👑 Принимаем заявки на две роли\nACADEMY/TEST 👑",
        color=discord.Color.from_rgb(255, 0, 0)
    )
    
    embed.description = (
        "**На роль TEST** требуются откаты с MCL/CAPT И GUNGAME.\n"
        "**Если претендуете на роль ACADEMY** — откаты не нужны.\n\n"
        "**Срок рассмотрения заявок:** от 1 до 3 рабочих дней. Решение направляется ботом в личные сообщения. "
        "Отсутствие ответа в указанный срок означает отказ в заявке.\n\n"
        "**Будем рады видеть вас в нашей семье!**\n\n"
        "⚠️ **Заявки в семью принимаются только на сервер Phoenix.**\n"
        "**ВСЕ ЗАЯВКИ МИНИМУМ ОТ 15 ЛЕТ!**\n\n"
        "Внимательно прочитайте шаблон заявки при её подаче — там тоже есть информация.\n"
        "В заявке на TEST требуются полные откаты с GG и МП (MCL, B33, Capt).\n"
        "Подавая заявку на роль TEST, не получится играть исключительно MCL и Капты, играть придется весь контент без исключения.\n\n"
        "**Дополнительные правила в заявке:**\n"
        "• Откаты с GG должны быть записаны не более **1 недели** назад.\n"
        "• Откаты с МП должны быть записаны не более **60 дней** назад.\n"
        "• Откаты не должны быть сделаны как нарезка или мувик.\n"
        "• Минимальная длина откатов с GG — **от 5 минут (спешал/тяжка/сайга) с таблицей счёта в конце.**\n"
        "• Любое нарушение условий подачи откатов будет причиной отказа без исключений.\n\n"
        "⚠️ После подачи заявки **следите за ЛС** или за запросами на общение в Discord. На обзвон рекрут позовёт вас **только в discord KARNAGE** — ни в ЛС, ни в другой сервер.\n\n"
        "В случае игнорирования рекрута в ЛС после принятия заявки — заявка будет **автоматически отклонена**, и вам нужно будет заново её оформлять.\n"
        "Если вам отказали — накладывается **КД 1 день** на ту же роль (Academy и Test считаются отдельно).\n\n"
        "**СЕРЬЁЗНО ОТНЕСИТЕСЬ К ШАБЛОНУ ПОДАЧИ.**\n"
        "Внимательно читайте и проверяйте все пункты заполнения. «Не увидел», «Плохо прочитал», «Не понял», «Пропустил» и т.д. будут рассматриваться как отказ."
    )
    
    embed.set_footer(text="KARNAGE | Phoenix")
    
    view = ApplyView()
    await ctx.send(embed=embed, view=view)

bot.run(TOKEN)