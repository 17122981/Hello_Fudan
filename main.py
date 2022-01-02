import json
import time
import os
from json import loads as json_loads
from os import path as os_path, getenv
from sys import exit as sys_exit
from getpass import getpass
import re
import base64
import io
import numpy
import requests
from PIL import Image
from PIL import ImageEnhance

from requests import session, post, adapters
adapters.DEFAULT_RETRIES = 5

def base64_api(uname, pwd, img, typeid):
    base64_data = base64.b64encode(img)
    b64 = base64_data.decode()
    data = {"username": uname, "password": pwd, "typeid": typeid, "image": b64}
    result = json.loads(requests.post("http://api.ttshitu.com/predict", json=data).text)
    return result

class Fudan:
    """
    建立与复旦服务器的会话，执行登录/登出操作
    """
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0"

    # 初始化会话
    def __init__(self,
                 uid, psw, shibie_name, shibie_psw,
                 url_login='https://uis.fudan.edu.cn/authserver/login',
                 url_code="https://zlapp.fudan.edu.cn/backend/default/code"):
        """
        初始化一个session，及登录信息
        :param uid: 学号
        :param psw: 密码
        :param shibie_name: “快识别”账户名
        :param shibie_psw: “快识别”密码
        :param url_login: 登录页，默认服务为空
        """
        self.session = session()
        self.session.keep_alive = False
        self.session.headers['User-Agent'] = self.UA
        self.url_login = url_login
        self.url_code = url_code

        self.uid = uid
        self.psw = psw
        self.shibie_name = shibie_name
        self.shibie_psw = shibie_psw

    def _page_init(self):
        """
        检查是否能打开登录页面
        :return: 登录页page source
        """
        print("◉Initiating——", end='')
        page_login = self.session.get(self.url_login)

        print("return status code",
              page_login.status_code)

        if page_login.status_code == 200:
            print("◉Initiated——", end="")
            return page_login.text
        else:
            print("◉Fail to open Login Page, Check your Internet connection\n")
            self.close()

    def login(self):
        """
        执行登录
        """
        page_login = self._page_init()

        print("getting tokens")
        data = {
            "username": self.uid,
            "password": self.psw,
            "service": "https://zlapp.fudan.edu.cn/site/ncov/fudanDaily"
        }

        # 获取登录页上的令牌
        result = re.findall(
            '<input type="hidden" name="([a-zA-Z0-9\-_]+)" value="([a-zA-Z0-9\-_]+)"/?>', page_login)
        # print(result)
        # result 是一个列表，列表中的每一项是包含 name 和 value 的 tuple，例如
        # [('lt', 'LT-6711210-Ia3WttcMvLBWNBygRNHdNzHzB49jlQ1602983174755-7xmC-cas'), ('dllt', 'userNamePasswordLogin'), ('execution', 'e1s1'), ('_eventId', 'submit'), ('rmShown', '1')]
        data.update(
            result
        )

        headers = {
            "Host": "uis.fudan.edu.cn",
            "Origin": "https://uis.fudan.edu.cn",
            "Referer": self.url_login,
            "User-Agent": self.UA
        }

        print("◉Login ing——", end="")
        post = self.session.post(
            self.url_login,
            data=data,
            headers=headers,
            allow_redirects=False)

        print("return status code", post.status_code)

        if post.status_code == 302:
            print("\n***********************"
                  "\n◉登录成功"
                  "\n***********************\n")
        else:
            print("◉登录失败，请检查账号信息")
            self.close()

    def logout(self):
        """
        执行登出
        """
        exit_url = 'https://uis.fudan.edu.cn/authserver/logout?service=/authserver/login'
        expire = self.session.get(exit_url).headers.get('Set-Cookie')
        # print(expire)

        if '01-Jan-1970' in expire:
            print("◉登出完毕")
        else:
            print("◉登出异常")

    def close(self, exit_code=0):
        """
        执行登出并关闭会话
        """
        self.logout()
        self.session.close()
        print("◉关闭会话")
        print("************************")
        sys_exit(exit_code)


class Zlapp(Fudan):
    last_info = ''

    def check(self):
        """
        检查
        """
        print("◉检测是否已提交")
        get_info = self.session.get(
            'https://zlapp.fudan.edu.cn/ncov/wap/fudan/get-info')
        last_info = get_info.json()

        print("◉上一次提交日期为:", last_info["d"]["info"]["date"])

        position = last_info["d"]["info"]['geo_api_info']
        position = json_loads(position)

        print("◉上一次提交地址为:", position['formattedAddress'])
        # print("◉上一次提交GPS为", position["position"])
        # print(last_info)
        
        # 改为上海时区
        os.environ['TZ'] = 'Asia/Shanghai'
        time.tzset()
        today = time.strftime("%Y%m%d", time.localtime())
        print("◉今日日期为:", today)
        if last_info["d"]["info"]["date"] == today:
            print("\n*******今日已提交*******")
            self.close()
        else:
            print("\n\n*******未提交*******")
            self.last_info = last_info["d"]["oldInfo"]    

    def validate_code(self):
        # ============== 设置 ============== #
        uname = self.shibie_name
        pwd = self.shibie_psw
        img = self.session.get(self.url_code).content
        typeid = 3
        
        result = base64_api(uname, pwd, img, typeid)
        if result['success']:
            return result["data"]["result"]
        else:
            return result["message"]
        return ""

    def checkin(self):
        """
        提交
        """
        headers = {
            "Host": "zlapp.fudan.edu.cn",
            "Referer": "https://zlapp.fudan.edu.cn/site/ncov/fudanDaily?from=history",
            "DNT": "1",
            "TE": "Trailers",
            "User-Agent": self.UA
        }

        print("\n\n◉◉提交中")

        geo_api_info = json_loads(self.last_info["geo_api_info"])
        province = self.last_info["province"]
        city = self.last_info["city"]
        district = geo_api_info["addressComponent"].get("district", "")
        
        while(True):
            print("◉正在识别验证码......")
            code = self.validate_code()
            print("◉验证码为:", code)
            self.last_info.update(
                {
                    "tw": "13",
                    "province": province,
                    "city": city,
                    "area": " ".join((province, city, district)),
                    #"sfzx": "1",  # 是否在校
                    #"fxyy": "",  # 返校原因
                    "code": code,
                }
            )
            # print(self.last_info)
            save = self.session.post(
                'https://zlapp.fudan.edu.cn/ncov/wap/fudan/save',
                data=self.last_info,
                headers=headers,
                allow_redirects=False)

            save_msg = json_loads(save.text)["m"]
            print(save_msg, '\n\n')
            time.sleep(0.1)
            if(json_loads(save.text)["e"] != 1):
                break

def get_account():
    """
    获取账号信息
    """
    uid = getenv("STD_ID")
    psw = getenv("PASSWORD")
    shibie_name = getenv("SHIBIE_NAME")
    shibie_psw = getenv("SHIBIE_PSW")
    print(uid, psw, shibie_name, shibie_psw)
    if uid != None and psw != None and shibie_name != None and shibie_psw != None:
        print("从环境变量中获取了用户名和密码！")
        return uid, psw, shibie_name, shibie_psw
    print("\n\n请仔细阅读以下日志！！\n请仔细阅读以下日志！！！！\n请仔细阅读以下日志！！！！！！\n\n")
    if os_path.exists("account.txt"):
        print("读取账号中……")
        with open("account.txt", "r") as old:
            raw = old.readlines()
        if (raw[0][:3] != "uid") or (len(raw[0]) < 10):
            print("account.txt 内容无效, 请手动修改内容")
            sys_exit()
        uid = (raw[0].split(":"))[1].strip()
        psw = (raw[1].split(":"))[1].strip()

    else:
        print("未找到account.txt, 判断为首次运行, 请接下来依次输入学号密码")
        uid = input("学号：")
        psw = getpass("密码：")
        with open("account.txt", "w") as new:
            tmp = "uid:" + uid + "\npsw:" + psw +\
                "\n\n\n以上两行冒号后分别写上学号密码，不要加空格/换行，谢谢\n\n请注意文件安全，不要放在明显位置\n\n可以从dailyFudan.exe创建快捷方式到桌面"
            new.write(tmp)
        print("账号已保存在目录下account.txt，请注意文件安全，不要放在明显位置\n\n建议拉个快捷方式到桌面")

    return uid, psw, shibie_name, shibie_psw


if __name__ == '__main__':
    uid, psw, shibie_name, shibie_psw = get_account()
    # print(uid, psw)
    zlapp_login = 'https://uis.fudan.edu.cn/authserver/login?' \
                  'service=https://zlapp.fudan.edu.cn/site/ncov/fudanDaily'
    code_url = "https://zlapp.fudan.edu.cn/backend/default/code"
    daily_fudan = Zlapp(uid, psw, shibie_name, shibie_psw,
                        url_login=zlapp_login, url_code=code_url)
    daily_fudan.login()

    daily_fudan.check()
    daily_fudan.checkin()
    # 再检查一遍
    daily_fudan.check()
    daily_fudan.close(1)
