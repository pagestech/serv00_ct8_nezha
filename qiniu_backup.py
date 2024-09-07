import os
from datetime import datetime
from typing import Dict, Optional
from logger_wrapper import LoggerWrapper
from sys_config_entry import SysConfigEntry
from qiniu import Auth, put_file, BucketManager
import qiniu.config

class QiniuBackup:
    _instance = None
    DATE_FORMAT = '%d_%H_%M'
    MONTH_FORMAT = '%Y%m'

    def __new__(cls, sys_config_entry: SysConfigEntry):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, sys_config_entry: SysConfigEntry):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True
        self.sys_config_entry = sys_config_entry
        self.logger = LoggerWrapper()
        self.access_key = self.sys_config_entry.get("QINIU_ACCESS_KEY")
        self.secret_key = self.sys_config_entry.get("QINIU_SECRET_KEY")
        self.region = self.sys_config_entry.get("QINIU_REGION")
        self.bucket_name = self.sys_config_entry.get("QINIU_BUCKET_NAME")
        self.dir_name = self.sys_config_entry.get("QINIU_DIR_NAME")
        self.ttl = int(self.sys_config_entry.get("QINIU_EXPIRE_DAYS", 7)) * 24 * 3600
        self.auth = Auth(self.access_key, self.secret_key)
        self.bucket_manager = BucketManager(self.auth)

    def _ensure_bucket_exists(self):
        try:
            buckets, _ = self.bucket_manager.list_bucket(self.region)
            if self.bucket_name not in buckets:
                ret, info = self.bucket_manager.mkbucketv3(self.bucket_name, self.region)
                if info.status_code == 200:
                    self.logger.info(f"====> 七牛成功创建 bucket: {self.bucket_name}")
                else:
                    self.logger.error(f"====> 七牛创建 bucket 失败: {self.bucket_name}, 错误信息: {info}")
            else:
                self.logger.info(f"====> 七牛Bucket 已存在: {self.bucket_name}")
        except Exception as e:
            self.logger.error(f"====> 七牛检查或创建 bucket 时出错: {str(e)}")

    def backup_dashboard_db(self, db_file: str) -> Optional[str]:
        try:
            self._ensure_bucket_exists()

            now = datetime.now()
            date_prefix = now.strftime(self.DATE_FORMAT)
            month_dir = now.strftime(self.MONTH_FORMAT)
            
            file_name = os.path.basename(db_file)
            new_file_name = f"{date_prefix}_{file_name}"
            upload_path = f"{self.dir_name}/{month_dir}/{new_file_name}"
            
            token = self.auth.upload_token(self.bucket_name, upload_path, self.ttl)
            
            ret, info = put_file(token, upload_path, db_file)
            if info.status_code == 200:
                self.logger.info(f"====> 上传到七牛成功 bucket_name={self.bucket_name} {upload_path}")
                return f"{self.bucket_name}/{upload_path}"
            else:
                self.logger.error(f"====> 上传到七牛失败 bucket_name={self.bucket_name} {upload_path} 错误信息: {info}")
                return None
        except Exception as e:
            self.logger.error(f"====> 上传到七牛失败 bucket_name={self.bucket_name} {upload_path} 错误：{str(e)}")
            return None
