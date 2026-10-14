import requests
from datetime import date
from dateutil.relativedelta import relativedelta
import urllib.parse
import json
from typing import Any, Dict, List, Optional, Union

class TronClassCourseAPI:
    def __init__(self, session):
        self.session = session

    async def get_courses(self):
        url = 'https://iclass.tku.edu.tw/api/my-courses?conditions={"status":["ongoing"]}'
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching courses: {str(e)}"}

    async def get_enrollments(self,course_id,data:dict=None):
        url = f"https://iclass.tku.edu.tw/api/course/{course_id}/enrollments"
        """
        data example:
        data = {"fields":"id,user(id,email,name,nickname,user_no,comment,grade(id,name),klass(id,name,code),department(id,name,code),org(id,name),program(id,name),user_attributes(tag)),roles,aliases,retake_status,seat_number,data,imported_from"}
        """
        try:
            if data is not None:
                response = self.session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json;charset=UTF-8"}
                )
            else:
                response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching enrollments: {str(e)}"}

    async def get_bulletins(self,org_mode:bool=False,start_date=None,end_date=None,page:int=1,size:int=10,course_ids:list=[]):
        base_url = 'https://iclass.tku.edu.tw/api/course-bulletins'
        if org_mode:
            base_url = 'https://iclass.tku.edu.tw/api/org-bulletin/bulletins'

        if end_date == None:
            end_date = date.today()
        
        if start_date == None:
            start_date = end_date - relativedelta(months=1)#one_month_ago
        
        conditions = {}
        if start_date == "" or end_date == "":
            # keep it empty string if user want to use default value
            conditions = {
            "start_date":"",
            "end_date": "",
            "keyword": "",
            "course_ids": course_ids
            }

        else:
            conditions = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "keyword": "",
            "course_ids": course_ids
            }

        query_string = urllib.parse.urlencode({
            "conditions": json.dumps(conditions),
            "page": page,
            "page_size": size
        })

        url = f"{base_url}?{query_string}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching bulletins: {str(e)}"}

    async def get_todos(self):
        todos_url = "https://iclass.tku.edu.tw/api/todos"
        try:
            response = self.session.get(todos_url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching todos: {str(e)}"}

    async def create_syllabus(
        self,
        module_id: Union[int, str] = None,
        date_str: Optional[str] = None,
        teaching_type: str = "face_to_face",
        summary: str = "",
        objective: str = "",
        comments: str = "",
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a syllabus entry for a module.
        POST https://iclass.tku.edu.tw/api/syllabus
        """
        url = "https://iclass.tku.edu.tw/api/syllabus"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=utf-8",
            "Origin": "https://iclass.tku.edu.tw",
        }
        payload: Dict[str, Any] = {
            "module_id": str(module_id) if module_id is not None else "",
            "teaching_type": teaching_type,
            "summary": summary,
            "objective": objective,
            "comments": comments,
            "date": date_str if date_str is not None else date.today().isoformat(),
        }
        if data:
            payload.update(data)
        if kwargs:
            payload.update(kwargs)

        try:
            response = self.session.post(url, headers=headers, json=payload)
            if response.ok:
                try:
                    return response.json()
                except ValueError:
                    return {"success": True, "status_code": response.status_code}
            else:
                try:
                    return {"error": f"Failed with status {response.status_code}", "details": response.json()}
                except ValueError:
                    return {"error": f"Failed with status {response.status_code}", "details": response.text}
        except requests.exceptions.RequestException as e:
            return {"error": f"Error creating syllabus: {str(e)}"}

    async def delete_module(
        self,
        module_id: Union[int, str],
        delete_related_activity: bool = True,
    ) -> Dict[str, Any]:
        """
        Delete a course module.
        DELETE https://iclass.tku.edu.tw/api/module/{module_id}?delete_related_activity=true
        """
        flag_str = "true" if delete_related_activity else "false"
        url = f"https://iclass.tku.edu.tw/api/module/{module_id}?delete_related_activity={flag_str}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://iclass.tku.edu.tw",
        }
        try:
            response = self.session.delete(url, headers=headers)
            if response.ok:
                try:
                    return response.json()
                except ValueError:
                    return {"success": True, "status_code": response.status_code}
            else:
                try:
                    return {"error": f"Failed with status {response.status_code}", "details": response.json()}
                except ValueError:
                    return {"error": f"Failed with status {response.status_code}", "details": response.text}
        except requests.exceptions.RequestException as e:
            return {"error": f"Error deleting module: {str(e)}"}

    async def get_course_access_code(self, course_id: int) -> Dict[str, Any]:
        """
        Get invitation access code for a course.
        GET https://iclass.tku.edu.tw/api/course/{course_id}/access_code
        """
        url = f"https://iclass.tku.edu.tw/api/course/{course_id}/access_code"
        headers = {
            "Accept": "application/json, text/plain, */*",
        }
        try:
            response = self.session.get(url, headers=headers)
            if response.ok:
                try:
                    return response.json()
                except ValueError:
                    return {"success": True, "status_code": response.status_code}
            else:
                try:
                    return {"error": f"Failed with status {response.status_code}", "details": response.json()}
                except ValueError:
                    return {"error": f"Failed with status {response.status_code}", "details": response.text}
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching course access code: {str(e)}"}