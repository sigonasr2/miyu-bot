import asyncio
import logging

import discord
from d4dj_utils.master.chart_master import ChartDifficulty, ChartMaster
from d4dj_utils.master.common_enums import ChartSectionType
from d4dj_utils.master.music_master import MusicMaster
from discord.ext import commands

from main import asset_manager
from miyu_bot.commands.common.fuzzy_matching import romanize, FuzzyMap


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.music = self.get_music()

    def get_music(self):
        music = FuzzyMap(lambda m: m.is_released)
        for m in asset_manager.music_master.values():
            music[f'{m.name} {m.special_unit_name}'] = m
        return music

    difficulty_names = {
        'expert': ChartDifficulty.Expert,
        'hard': ChartDifficulty.Hard,
        'normal': ChartDifficulty.Normal,
        'easy': ChartDifficulty.Easy,
        'exp': ChartDifficulty.Expert,
        'hrd': ChartDifficulty.Hard,
        'nrm': ChartDifficulty.Normal,
        'esy': ChartDifficulty.Easy,
        'ex': ChartDifficulty.Expert,
        'hd': ChartDifficulty.Hard,
        'nm': ChartDifficulty.Normal,
        'es': ChartDifficulty.Easy,
    }

    @staticmethod
    def format_info(info_entries: dict):
        return '\n'.join(f'{k}: {v}' for k, v in info_entries.items() if v)

    @commands.command(name='song',
                      aliases=['music'],
                      description='Finds the song with the given name.',
                      help='!song grgr')
    async def song(self, ctx: commands.Context, *, arg: str):
        self.logger.info(f'Searching for song "{arg}".')

        song: MusicMaster = self.music[arg]
        if not song:
            msg = f'Failed to find song "{arg}".'
            await ctx.send(msg)
            self.logger.info(msg)
            return
        self.logger.info(f'Found "{song}" ({romanize(song.name)[1]}).')

        thumb = discord.File(song.jacket_path, filename='jacket.png')

        embed = discord.Embed(title=song.name)
        embed.set_thumbnail(url=f'attachment://jacket.png')

        artist_info = {
            'Lyricist': song.lyricist,
            'Composer': song.composer,
            'Arranger': song.arranger,
            'Unit': song.unit.name,
            'Special Unit Name': song.special_unit_name,
        }

        music_info = {
            'Category': song.category.name,
            'BPM': song.bpm,
            'Section Trend': song.section_trend.name,
            'Sort Order': song.default_order,
            'Levels': ', '.join(c.display_level for c in song.charts.values()),
            'Release Date': song.start_datetime,
        }

        embed.add_field(name='Artist',
                        value=self.format_info(artist_info),
                        inline=False)
        embed.add_field(name='Info',
                        value=self.format_info(music_info),
                        inline=False)

        await ctx.send(files=[thumb], embed=embed)

    @commands.command(name='chart',
                      aliases=[],
                      description='Finds the chart with the given name.',
                      help='!chart grgr\n!chart grgr normal')
    async def chart(self, ctx: commands.Context, *, arg: str):
        self.logger.info(f'Searching for chart "{arg}".')

        split_args = arg.split()

        difficulty = ChartDifficulty.Expert
        if len(split_args) >= 2:
            final_word = split_args[-1]
            if final_word in self.difficulty_names:
                difficulty = self.difficulty_names[final_word]
                arg = ''.join(split_args[:-1])

        song: MusicMaster = self.music[arg]
        if not song:
            msg = f'Failed to find chart "{arg}".'
            await ctx.send(msg)
            self.logger.info(msg)
            return
        self.logger.info(f'Found "{song}" ({romanize(song.name)[1]}).')

        embeds, files = self.get_chart_embed_info(song)

        message = await ctx.send(files=files, embed=embeds[difficulty - 1])

        reaction_emote_ids = [
            790050636568723466,
            790050636489555998,
            790050636548276252,
            790050636225052694,
        ]

        for emote_id in reaction_emote_ids:
            await message.add_reaction(self.bot.get_emoji(emote_id))

        def check(rxn, usr):
            return usr == ctx.author and rxn.emoji.id in reaction_emote_ids

        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=check)
                self.logger.debug(f'Reaction {reaction} from user {user}.')
                emote_index = reaction_emote_ids.index(reaction.emoji.id)
                await message.edit(embed=embeds[emote_index])
                await message.remove_reaction(reaction, user)
            except asyncio.TimeoutError:
                break

    def get_chart_embed_info(self, song):
        embeds = []
        files = [discord.File(song.jacket_path, filename=f'jacket.png')]
        for difficulty in [ChartDifficulty.Easy, ChartDifficulty.Normal, ChartDifficulty.Hard, ChartDifficulty.Expert]:
            chart = song.charts[difficulty]
            embed = discord.Embed(title=f'{song.name} [{chart.difficulty.name}]')
            embed.set_thumbnail(url=f'attachment://jacket.png')
            embed.set_image(
                url=f'https://qwewqa.github.io/d4dj-dumps/{chart.image_path.relative_to(asset_manager.path).as_posix()}'
            )

            chart_data = chart.load_chart_data()
            note_counts = chart_data.get_note_counts()

            embed.add_field(name='Info',
                            value=f'Level: {chart.display_level}\n'
                                  f'Unit: {song.special_unit_name or song.unit.name}\n'
                                  f'Category: {song.category.name}\n'
                                  f'BPM: {song.bpm}',
                            inline=False)
            embed.add_field(name='Combo',
                            value=f'Max Combo: {chart.note_counts[ChartSectionType.Full].count}\n'
                                  f'Taps: {note_counts["tap"]} (dark: {note_counts["tap1"]}, light: {note_counts["tap2"]})\n'
                                  f'Scratches: {note_counts["scratch"]} (left: {note_counts["scratch_left"]}, right: {note_counts["scratch_right"]})\n'
                                  f'Stops: {note_counts["stop"]} (head: {note_counts["stop_start"]}, tail: {note_counts["stop_end"]})\n'
                                  f'Long: {note_counts["long"]} (head: {note_counts["long_start"]}, tail: {note_counts["long_end"]})\n'
                                  f'Slide: {note_counts["slide"]} (tick: {note_counts["slide_tick"]}, flick {note_counts["slide_flick"]})',
                            inline=True)
            embed.add_field(name='Ratings',
                            value=f'NTS: {round(chart.trends[0] * 100, 2)}%\n'
                                  f'DNG: {round(chart.trends[1] * 100, 2)}%\n'
                                  f'SCR: {round(chart.trends[2] * 100, 2)}%\n'
                                  f'EFT: {round(chart.trends[3] * 100, 2)}%\n'
                                  f'TEC: {round(chart.trends[4] * 100, 2)}%\n',
                            inline=True)
            embed.set_footer(text='1 column = 10 seconds')

            embeds.append(embed)

        return embeds, files


def setup(bot):
    bot.add_cog(Music(bot))
