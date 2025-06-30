#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/6/30 14:18
# @Author  : Soin
# @File    : demo.py
# @Software: PyCharm
import re
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
from loguru import logger
import time
import random
from concurrent.futures import ThreadPoolExecutor


class RequestsWrapper:
    def __init__(self, retries=3, backoff_factor=0.3, timeout=10, status_forcelist=(500, 502, 504)):
        self.session = requests.Session()
        self.timeout = timeout

        # 配置重试策略
        retry_strategy = Retry(
            total=retries,
            status_forcelist=status_forcelist,
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            backoff_factor=backoff_factor,
            raise_on_status=False
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()  # 若响应为 4xx 或 5xx，会抛出异常
            return response
        except requests.RequestException as e:
            print(f"[ERROR] Request to {url} failed: {e}")
            return None

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


result_path = os.path.join(os.getcwd(), 'pdf_result')
http = RequestsWrapper(retries=5, backoff_factor=1)


def support_content(ProductNodePath, Page):
    """
        这个函数实现获取SupportContent 数据内容,这个内容包含不同语言的pdf下载路径
    :return:
    """
    headers = {
        'sec-ch-ua-platform': '"Windows"',
        'X-Version': 'v1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Authorization': f'Bearer {access_token()}',
        'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'ADRUM': 'isAjax:true',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        # "x-correlation-id": "a50d244a-737e-4e29-badb-5016919f2dc9"
    }

    params = {
        'region': 'cn',
        'language': 'zh',
        'EntryTypes': 'Manual',
        'SearchTerm': '',
        'ProductNodePath': f'/{ProductNodePath}/',
        'SortingOption': 'CreationDateDesc',
        'Page': str(Page),
        'PageSize': '20',
    }

    response = http.get('https://sieportal.siemens.com/api/sios/api/Search/SupportContent',
                        params=params, headers=headers)
    # 正常解析
    support_contents = response.json()['supportContent']
    for support in support_contents:
        language_codes = [language['languageCode'] for language in support['languages']]
        entry_id = support['entryId']
        # 获取到result_path下的文件夹名称
        if str(entry_id) in os.listdir(result_path):
            logger.debug(f"{entry_id},已采集,跳过这个")
            continue

        if len(language_codes) <= 1 or 'zh' not in language_codes:  # 如果语言类型里面没有中文就或者只有一种或一种一下的语言就跳过
            continue
        else:
            with ThreadPoolExecutor(max_workers=5) as executor:
                for language_code in language_codes:  # 循环获取不同语言的pdf下载地址
                    logger.info(f"正在下载:{support['title']},{language_code}的pdf文件")
                    executor.submit(get_pdf_link, locale_group_id=entry_id, language=language_code)


# def down_pdf(url, headers, down_path):
#     logger.info(f"🚀 正在开始下载：{url}")
#
#     # 发起带流的 GET 请求
#     response = http.get(url, headers=headers, stream=True)
#     if not response or response.status_code != 200:
#         logger.error("❌ 下载失败")
#         return
#     # 获取总大小（字节）
#     total_size = int(response.headers.get('content-length', 0))
#     # 用 tqdm 包装写入过程，实现进度条
#     with open(down_path, 'wb') as f, tqdm(
#             desc=f"\033[92m📥 下载中: {down_path}\033[0m",  # 定义前置文本
#             total=total_size,  # 比例后置数字
#             unit='B',  # 这个应该是进度条大小
#             unit_scale=True,  # 显示进度条
#             unit_divisor=1024,  # 每次写入的字符大小
#             ncols=200,  # desc+进度条的文本长度，超过了就不会显示进度条
#             colour='white'  # 定义进度条颜色
#     ) as bar:
#
#         for chunk in response.iter_content(chunk_size=1024):
#             if chunk:
#                 f.write(chunk)
#                 bar.update(len(chunk))
#
#     logger.success(f"✅ 下载完成！存储位置：{down_path}")

def down_pdf(url, headers, down_path):
    logger.info(f"🚀 正在开始下载：{url}")

    # 发起带流的 GET 请求
    response = http.get(url, headers=headers, stream=True)
    if not response or response.status_code != 200:
        logger.error("❌ 下载失败")
        return
    # 获取总大小（字节）
    total_size = int(response.headers.get('content-length', 0))

    # 用 tqdm 包装写入过程，实现进度条
    with open(down_path, 'wb') as f:
        f.write(response.content)

    logger.success(f"✅ 下载完成！总字节长度：{total_size}存储位置：{down_path}")


def get_pdf_link(locale_group_id: int, language: str):
    headers = {
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }

    params = {
        'localeGroupId': str(locale_group_id),
        'language': language,
        'networks': 'Internet',
        'region': 'cn',
    }

    response = http.get(
        'https://support.industry.siemens.com/webbackend/api/DocumentContents/DetailedDocument',
        params=params,
        headers=headers,
    ).json()
    pdf_link = f'https://support.industry.siemens.com/{response['PdfLink']}?download=true'  # 通过这个链接接重定向到下载地址
    true_pdf_link = http.get(pdf_link, headers=headers).url
    load_path = os.path.join(os.getcwd(), 'pdf_result', str(locale_group_id))
    os.makedirs(load_path, exist_ok=True)
    down_pdf(true_pdf_link, headers, f"{load_path}\\{language}.pdf")


def access_token():
    headers = {
        'sec-ch-ua-platform': '"Windows"',
        'Cache-Control': 'no-cache',
        'Referer': 'https://sieportal.siemens.com/',
        'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    data = {
        'client_id': 'Siemens.SiePortal.UI',
        'client_secret': client_secret(),
        'grant_type': 'client_credentials',
    }

    response = http.post('https://auth.sieportal.siemens.com/connect/token', headers=headers, data=data)
    access_token = response.json()['access_token']
    return access_token


def client_secret():
    headers = {
        'Origin': 'https://sieportal.siemens.com',
        'sec-ch-ua-platform': '"Windows"',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
    }
    response = http.get('https://sieportal.siemens.com/assets/environments/environment.js', headers=headers).text
    return re.search(r"client_secret: '(.*?)'", response).group(1)


def main():
    main_dic = [{"id": 13204, "num": 412},  # 驱动技术
                {"id": 13613, "num": 3885},  # 自动化技术
                {"id": 24186, "num": 454}]  # 楼宇科技
    for dic in main_dic:
        ProductNodePath = dic['id']
        max_page = dic['num'] / 20 + 2
        for page in range(1, int(max_page)):
            logger.info(f"正在采集{ProductNodePath}第{page}页数据......")
            support_content(ProductNodePath, page)
            time.sleep(random.uniform(1, 2))


if __name__ == '__main__':
    # 获取到result_path下的文件夹名称
    main()
