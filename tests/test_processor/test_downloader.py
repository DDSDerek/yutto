from __future__ import annotations

import asyncio

import aiohttp
import pytest

from yutto.processor.downloader import slice_blocks
from yutto.utils.fetcher import Fetcher
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.funcutils import as_sync

from ..conftest import TEST_DIR


@pytest.mark.processor
@as_sync
async def test_150_kB_downloader():
    # test_dir = "./downloader_test/"
    # url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"
    # 因为 file-examples-com 挂掉了（GitHub 账号都消失了，因此暂时使用一个别处的 mirror）
    url = "https://github.com/nhegde610/samples-files/raw/main/file_example_MP4_480_1_5MG.mp4"
    file_path = TEST_DIR / "test_150_kB.pdf"
    async with await AsyncFileBuffer(file_path, overwrite=False) as buffer:
        async with aiohttp.ClientSession(
            headers=Fetcher.headers,
            cookies=Fetcher.cookies,
            trust_env=Fetcher.trust_env,
            timeout=aiohttp.ClientTimeout(connect=5, sock_read=10),
        ) as session:
            Fetcher.set_semaphore(4)
            size = await Fetcher.get_size(session, url)
            coroutines = [
                Fetcher.download_file_with_offset(session, url, [], buffer, offset, block_size)
                for offset, block_size in slice_blocks(buffer.written_size, size, 1 * 1024 * 1024)
            ]

            print("开始下载……")
            await asyncio.gather(*coroutines)
            print("下载完成！")
            assert size == file_path.stat().st_size, "文件大小与实际大小不符"


@pytest.mark.processor
@as_sync
async def test_150_kB_no_slice_downloader():
    # test_dir = "./downloader_test/"
    # url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"
    url = "https://github.com/nhegde610/samples-files/raw/main/file_example_MP4_480_1_5MG.mp4"
    file_path = TEST_DIR / "test_150_kB_no_slice.pdf"
    async with await AsyncFileBuffer(file_path, overwrite=False) as buffer:
        async with aiohttp.ClientSession(
            headers=Fetcher.headers,
            cookies=Fetcher.cookies,
            trust_env=Fetcher.trust_env,
            timeout=aiohttp.ClientTimeout(connect=5, sock_read=10),
        ) as session:
            Fetcher.set_semaphore(4)
            size = await Fetcher.get_size(session, url)
            coroutines = [Fetcher.download_file_with_offset(session, url, [], buffer, 0, size)]

            print("开始下载……")
            await asyncio.gather(*coroutines)
            print("下载完成！")
            assert size == file_path.stat().st_size, "文件大小与实际大小不符"
