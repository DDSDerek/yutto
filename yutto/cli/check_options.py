import argparse
import asyncio
import os
import sys

import aiohttp

from yutto.api.info import is_vip
from yutto.media.codec import audio_codec_priority_default, video_codec_priority_default
from yutto.processor.crawler import gen_cookies, gen_headers
from yutto.utils.asynclib import install_uvloop
from yutto.utils.console.colorful import set_no_color
from yutto.utils.console.logger import Badge, Logger, set_logger_debug
from yutto.utils.ffmpeg import FFmpeg
from yutto.processor.filter import check_episodes


def check_basic_options(args: argparse.Namespace):
    """ 检查 argparse 无法检查的选项，并设置某些全局变量 """

    ffmpeg = FFmpeg()

    # 在使用 --no-color 或者环境变量 NO_COLOR 非空时都应该不显示颜色
    # See also: https://no-color.org/
    if args.no_color or os.environ.get("NO_COLOR"):
        set_no_color()

    # debug 设置
    if args.debug:
        set_logger_debug()
    else:
        # 为保证协程错误栈的可读性，debug 模式不启用 uvloop
        install_uvloop()

    # vcodec 检查
    vcodec_splited = args.vcodec.split(":")
    if len(vcodec_splited) != 2:
        Logger.error("vcodec 参数值（{}）不满足要求（并非使用 : 分隔的值）".format(args.vcodec))
        sys.exit(1)
    video_download_codec, video_save_codec = vcodec_splited
    if video_download_codec not in video_codec_priority_default:
        Logger.error(
            "download_vcodec 参数值（{}）不满足要求（允许值：{{{}}}）".format(
                video_download_codec, ", ".join(video_codec_priority_default)
            )
        )
        sys.exit(1)
    if video_save_codec not in ffmpeg.video_encodecs + ["copy"]:
        Logger.error(
            "save_vcodec 参数值（{}）不满足要求（允许值：{{{}}}）".format(video_save_codec, ", ".join(ffmpeg.video_encodecs + ["copy"]))
        )
        sys.exit(1)

    # acodec 检查
    acodec_splited = args.acodec.split(":")
    if len(acodec_splited) != 2:
        Logger.error("acodec 参数值（{}）不满足要求（并非使用 : 分隔的值）".format(args.acodec))
        sys.exit(1)
    audio_download_codec, audio_save_codec = acodec_splited
    if audio_download_codec not in audio_codec_priority_default:
        Logger.error(
            "download_acodec 参数值（{}）不满足要求（允许值：{{{}}}）".format(
                audio_download_codec, ", ".join(audio_codec_priority_default)
            )
        )
        sys.exit(1)
    if audio_save_codec not in ffmpeg.audio_encodecs + ["copy"]:
        Logger.error(
            "save_acodec 参数值（{}）不满足要求（允许值：{{{}}}）".format(audio_save_codec, ", ".join(ffmpeg.audio_encodecs + ["copy"]))
        )
        sys.exit(1)

    # only_video 和 only_audio 不能同时设置
    if not args.require_video and not args.require_audio:
        Logger.error("only_video 和 only_audio 不能同时设置")
        sys.exit(1)

    # TODO: proxy 检验

    # 不下载视频无法嵌入字幕
    if not args.require_video and args.embed_subtitle:
        Logger.error("不下载视频时无法嵌入字幕")
        sys.exit(1)

    # 不下载视频无法嵌入弹幕
    if not args.require_video and args.embed_danmaku:
        Logger.error("不下载视频时无法嵌入弹幕")
        sys.exit(1)

    # 不下载视频无法生成 ASS 弹幕（ASS 弹幕生成计算依赖于视频分辨率大小）
    if not args.require_video and args.danmaku == "ass":
        Logger.error("不下载视频无法生成 ASS 弹幕")
        sys.exit(1)

    # 嵌入弹幕功能仅支持 ASS 弹幕
    if args.embed_danmaku and args.danmaku != "ass":
        Logger.error("嵌入弹幕功能仅支持 ASS 弹幕")
        sys.exit(1)

    # 大会员身份校验
    if not args.sessdata:
        Logger.warning("未提供 SESSDATA，无法下载会员专享剧集")
    elif asyncio.run(check_is_vip(args.sessdata)):
        Logger.custom("成功以大会员身份登录～", badge=Badge("大会员", fore="white", back="magenta"))
    else:
        Logger.warning("以非大会员身份登录，无法下载会员专享剧集")


def check_batch_options(args: argparse.Namespace):
    """ 检查批量下载相关选项 """
    # 检查 episodes 格式（简单的正则检查，后续过滤剧集时还有完整检查）
    if not check_episodes(args.episodes):
        Logger.error("选集参数（{}）格式不正确".format(args.episodes))
        sys.exit(1)


async def check_is_vip(sessdata: str = "") -> bool:
    async with aiohttp.ClientSession(
        headers=gen_headers(), cookies=gen_cookies(sessdata), timeout=aiohttp.ClientTimeout(total=5)
    ) as session:
        return await is_vip(session)