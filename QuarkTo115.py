#!/usr/bin/python3
# -*- encoding: utf-8 -*-
"""
@File    :   alist_strm_115.py
@Desc    :   QuarkTo115简化版
@Version :   v1.1
@Time    :   2025/12/07
@Author  :   guogang
@Contact :   awordx@163.com
"""
import os
import re
import json
import requests

class Alist_strm_115:

    video_exts = ["mp4", "mkv", "flv", "mov", "m4v", "avi", "webm", "wmv"]
    default_config = {
        "url": "",  # Alist 服务器 URL
        "token": "",  # Alist 服务器 Token
        "storage_id": "",  # Alist 服务器夸克存储 ID
        "strm_save_dir": "/media",  # 生成的 strm 文件保存的路径
        "strm_replace_host": "",  # strm 文件内链接的主机地址 （可选，缺省时=url）
    }
    default_task_config = {
        "auto_gen": True,  # 是否自动生成 strm 文件
    }
    is_active = False
    # 缓存参数
    storage_mount_path = None
    quark_root_dir = None
    strm_server = None

    def __init__(self, **kwargs):
        self.plugin_name = self.__class__.__name__.lower()#使用前请修改以下七项参数
        self.alist_token = 'openlist-*****'#openlist的token
        self.new_folder_url = 'https://****/api/fs/mkdir'#  ****代表openlist的ip例如：192.168.8.106:5244
        self.copy_file_url = 'https://****/api/fs/copy'#同上 openlist的ip
        self.get_folder_files_url = "https://****/api/fs/list"#同上 openlist的ip
        self.password = '*****'#openlist的登录密码
        self.anime_path115 = '/115_15TB/动漫New'#自动把夸克下的动漫转存到alist的此目录（此目录是openlist的挂载目录）
        self.anime_pathquark = '/夸克/动漫'#监控的夸克网盘的转存目录，只会将此目录下的新增资源进行转存（此目录的根路径是夸克网盘的根路径）

        if kwargs:
            for key, _ in self.default_config.items():
                if key in kwargs:
                    setattr(self, key, kwargs[key])
                else:
                    print(f"{self.plugin_name} 模块缺少必要参数: {key}")
            if self.url and self.token and self.storage_id:
                success, result = self.storage_id_to_path(self.storage_id)
                if success:
                    self.is_active = True
                    # 存储挂载路径, 夸克根文件夹
                    self.storage_mount_path, self.quark_root_dir = result
                    # 替换strm文件内链接的主机地址
                    self.strm_replace_host = self.strm_replace_host.strip()
                    if self.strm_replace_host:
                        if self.strm_replace_host.startswith("http"):
                            self.strm_server = f"{self.strm_replace_host}/d"
                        else:
                            self.strm_server = f"http://{self.strm_replace_host}/d"
                    else:
                        self.strm_server = f"{self.url.strip()}/d"
    def copy_file(self,src_dir,dst_dir,file_names):
        url = self.copy_file_url
        payload = json.dumps({
            "src_dir": src_dir,
            "dst_dir": dst_dir,
            "names": [file_names]
        })
        headers = {
            'Authorization': self.alist_token,
            'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload).json()
        if response.get('code') == 200:
            print(f"{file_names}从{src_dir}复制到了{dst_dir}")
        else:
            print(f"Error: {response.get('message')}，此错误与alist的api相关，可能115的cookies失效了")
    def create_new_folder(self,folder_ptah):
        url = self.new_folder_url
        payload = json.dumps({
            "path": folder_ptah,
        })
        headers = {
            'Authorization': self.alist_token,
            'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload).json()
        if response.get('code') == 200:
            print(f"Successfully create folder {folder_ptah}")
        else:
            print(f"Error: {response.get('message')}，此错误与alist的api相关，可能115的cookies失效了")
    def run(self, task, **kwargs):
        task_config = task.get("addition", {}).get(
            self.plugin_name, self.default_task_config
        )
        if not task_config.get("auto_gen"):
            return
        if task.get("savepath") and task.get("savepath").startswith(
            self.quark_root_dir
        ):
            alist_path = os.path.normpath(
                os.path.join(
                    self.storage_mount_path,
                    task["savepath"].replace(self.quark_root_dir, "", 1).lstrip("/"),
                )
            ).replace("\\", "/")
            self.check_dir(alist_path)

    def storage_id_to_path(self, storage_id):
        storage_mount_path, quark_root_dir = None, None
        # 1. 检查是否符合 /aaa:/bbb 格式
        if match := re.match(r"^(\/[^:]*):(\/[^:]*)$", storage_id):
            # 存储挂载路径, 夸克根文件夹
            storage_mount_path, quark_root_dir = match.group(1), match.group(2)
            file_list = self.get_file_list(storage_mount_path)
            if file_list.get("code") != 200:
                print(f"Alist-Strm生成: 获取挂载路径失败❌ {file_list.get('message')}")
                return False, (None, None)
        # 2. 检查是否数字，调用 Alist API 获取存储信息
        elif re.match(r"^\d+$", storage_id):
            if storage_info := self.get_storage_info(storage_id):
                if storage_info["driver"] == "Quark":
                    addition = json.loads(storage_info["addition"])
                    # 存储挂载路径
                    storage_mount_path = storage_info["mount_path"]
                    # 夸克根文件夹
                    quark_root_dir = self.get_root_folder_full_path(
                        addition["cookie"], addition["root_folder_id"]
                    )
                elif storage_info["driver"] == "QuarkTV":
                    print(
                        f"Alist-Strm生成: [QuarkTV]驱动⚠️ storage_id请手动填入 /Alist挂载路径:/Quark目录路径"
                    )
                else:
                    print(f"Alist-Strm生成: 不支持[{storage_info['driver']}]驱动 ❌")
        else:
            print(f"Alist-Strm生成: storage_id[{storage_id}]格式错误❌")
        # 返回结果
        if storage_mount_path and quark_root_dir:
            print(f"Alist-Strm生成: [{storage_mount_path}:{quark_root_dir}]")
            return True, (storage_mount_path, quark_root_dir)
        else:
            return False, (None, None)

    def get_storage_info(self, storage_id):
        url = f"{self.url}/api/admin/storage/get"
        headers = {"Authorization": self.token}
        querystring = {"id": storage_id}
        try:
            response = requests.request("GET", url, headers=headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200:
                return data.get("data", [])
            else:
                print(f"Alist-Strm生成: 获取存储失败❌ {data.get('message')}")
        except Exception as e:
            print(f"Alist-Strm生成: 获取存储出错 {e}")
        return []

    def check_dir(self, path):
        data = self.get_file_list(path)
        if data.get("code") != 200:
            print(f"ߓꠁlist-Strm生成: 获取文件列表失败❌{data.get('message')}")
            return
        elif files := data.get("data", {}).get("content"):
            for item in files:
                item_path = f"{path}/{item.get('name')}".replace("//", "/")
                if item.get("is_dir"):
                    self.check_dir(item_path)
                else:
                    self.generate_strm(item_path)

    def get_file_list(self, path, force_refresh=False):
        url = f"{self.url}/api/fs/list"
        headers = {"Authorization": self.token}
        payload = {
            "path": path,
            "refresh": force_refresh,
            "password": "",
            "page": 1,
            "per_page": 0,
        }
        try:
            response = requests.request("POST", url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"ߓꠁlist-Strm生成: 获取文件列表出错❌ {e}")
        return {}
    def get_folder_files(self,folder_path,refresh=True,need_content=False):
        url = self.get_folder_files_url
        payload = json.dumps({
           "path": folder_path,
           "password": self.password,
           "page": 1,
           "per_page": 0,
           "refresh": refresh
        })
        headers = {
           'Authorization': self.alist_token,
           'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
           'Content-Type': 'application/json'
        }

        allfiles = requests.request("POST", url, headers=headers, data=payload).json()
        if allfiles.get('code') == 200 and allfiles['data']['content'] is not None:
            names = [item['name'] for item in allfiles['data']['content']]
        elif allfiles.get('code') == 500:
            print(
                f'未找到[{folder_path}]文件夹，可能此文件夹不存在')
            names = False
            # sys.exit(1)
        else:
            print(f"Error: {allfiles.get('message')}")
            names = None
        if need_content:
            return names,allfiles
        else:
            return names

    def generate_strm(self, file_path):
        ext = file_path.split(".")[-1]
        if ext.lower() in self.video_exts:
            strm_path = (
                f"{self.strm_save_dir}{os.path.splitext(file_path)[0]}.strm".replace(
                    "//", "/"
                )
            )

            # 替换路径
            original_path = self.anime_pathquark#"/夸克/动漫"
            new_base_url = self.anime_path115#"/115_15TB/动漫test"
            # 替换为新的 URL

            file_path = file_path.replace(original_path, new_base_url)
            print(f'获取到file_path{file_path}')

            #生成剧集名字目录#  
            directory_path = os.path.dirname(file_path)
            final_directory_path = directory_path.replace(self.anime_path115, "")
            anime_path = os.path.normpath(final_directory_path)


            src_path = self.anime_pathquark+anime_path 
            self.create_new_folder(self.anime_path115+anime_path)
            print(f"创建了文件夹:{self.anime_path115+anime_path}")
            dst_path = self.anime_path115+anime_path   
            copyfile_name = os.path.basename(file_path)
            print(f'src_path:{src_path},dst_path:{dst_path},copyfile_name{copyfile_name}')
            files = self.get_folder_files(dst_path,refresh=False)
            if files is None:
                self.copy_file(src_path, dst_path, copyfile_name)
                print('成功复制文件')
            if files is not None and copyfile_name not in files:
                self.copy_file(src_path, dst_path, copyfile_name)
                print('成功复制文件')

 
            if os.path.exists(strm_path):
                return
            if not os.path.exists(os.path.dirname(strm_path)):
                os.makedirs(os.path.dirname(strm_path))
            with open(strm_path, "w", encoding="utf-8") as strm_file:
                strm_file.write(f"{self.strm_server}{file_path}")
            print(f"ߓꠧ䟦萓TRM文件 {strm_path} 成功✅")

    def get_root_folder_full_path(self, cookie, pdir_fid):
        if pdir_fid == "0":
            return "/"
        url = "https://drive-h.quark.cn/1/clouddrive/file/sort"
        headers = {
            "cookie": cookie,
            "content-type": "application/json",
        }
        querystring = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "pdir_fid": pdir_fid,
            "_page": 1,
            "_size": "50",
            "_fetch_total": "1",
            "_fetch_sub_dirs": "0",
            "_sort": "file_type:asc,updated_at:desc",
            "_fetch_full_path": 1,
        }
        try:
            response = requests.request(
                "GET", url, headers=headers, params=querystring
            ).json()
            if response["code"] == 0:
                path = ""
                for item in response["data"]["full_path"]:
                    path = f"{path}/{item['file_name']}"
                return path
        except Exception as e:
            print(f"Alist-Strm生成: 获取Quark路径出错 {e}")
        return ""

