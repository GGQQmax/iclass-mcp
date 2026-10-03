# -*- coding: utf-8 -*-
import os
import requests
from dotenv import load_dotenv
import json
import re
from texttable import Texttable

"""
 this api is not been used
"""


class IifeAPI:
    def __init__(self):
        load_dotenv()
        self.__genkey = os.getenv("GENKEY")
        self.session = requests.Session()
    
    async def get_StuClass(self):
        url = f"https://ilifeapi.az.tku.edu.tw/api/ilifeStuClassApi?q={self.__genkey}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = 'utf-8' 
            return response.text
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching StuClass: {str(e)}"}

    
    async def displayStuClass(self,lang="ch",size=22):
        stuClass = [[0 for _ in range(14)] for _ in range(6)]
        try:
            data = await self.get_StuClass()
            jsonObj = json.loads(data)
            cellStdClass = jsonObj["cells"]

            for i, item in enumerate(cellStdClass):
                text = re.sub(r'[\(（][^)\）]*[\)）]', '', cellStdClass[i][f"{lang}_cos_name"])
                text  = text+cellStdClass[i]["room"]
                #print(text, "\t", end="")
                weekNo = int(cellStdClass[i]["weekno"])-1
                sessNo = int(cellStdClass[i]["sessno"])-1
                stuClass[weekNo][sessNo] = text

            t = Texttable()
            t.set_cols_width([size] * 5)
            t.add_row(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            for i in range(10):
                    #print(row,end="\t")
                t.add_row([stuClass[j][i].ljust(size) for j in range(5)])
            print(t.draw())

        except Exception as e:
            print(f"Unexpected error: {str(e)}")
