import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.header import Header
from config.settings import settings
from loguru import logger


class EmailService:
    """邮件服务类"""
    
    def __init__(self):
        # 不在__init__中缓存配置，每次使用时动态读取
        pass
    
    @property
    def smtp_host(self):
        return settings.smtp_host
    
    @property
    def smtp_port(self):
        return settings.smtp_port
    
    @property
    def smtp_username(self):
        return settings.smtp_username
    
    @property
    def smtp_password(self):
        return settings.smtp_password
    
    @property
    def smtp_use_tls(self):
        return settings.smtp_use_tls
    
    def send_email(self, to_email: str, subject: str, body: str, html_body: str = None) -> bool:
        """
        发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件纯文本内容
            html_body: 邮件HTML内容（可选）
            
        Returns:
            bool: 发送成功返回True，失败返回False
        """
        try:
            # 创建邮件对象
            message = MIMEMultipart("alternative")
            message["Subject"] = Header(subject, 'utf-8')
            # 修复From字段格式，符合RFC标准
            message["From"] = str(Header("Stellarmind", 'utf-8')) + f" <{self.smtp_username}>"
            message["To"] = to_email
            
            # 创建纯文本部分
            text_part = MIMEText(body, "plain", "utf-8")
            message.attach(text_part)
            
            # 如果提供了HTML内容，添加HTML部分
            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                message.attach(html_part)
            
            # 连接SMTP服务器并发送邮件
            logger.info(f"SMTP配置: host={self.smtp_host}, port={self.smtp_port}, username={self.smtp_username}, use_tls={self.smtp_use_tls}")
            
            # 企业微信邮箱使用465端口SSL，阿里云使用587端口TLS
            if self.smtp_port == 465:
                # 使用SSL连接（企业微信推荐）
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context)
                logger.info(f"已连接到SMTP服务器（SSL）: {self.smtp_host}:{self.smtp_port}")
            elif self.smtp_use_tls:
                # 使用TLS连接（阿里云等）
                context = ssl.create_default_context()
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                logger.info(f"已连接到SMTP服务器: {self.smtp_host}:{self.smtp_port}")
                server.starttls(context=context)
                logger.info("TLS已启用")
            else:
                # 普通连接
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                logger.info(f"已连接到SMTP服务器: {self.smtp_host}:{self.smtp_port}")
            
            logger.info(f"尝试登录SMTP服务器: {self.smtp_username}")
            server.login(self.smtp_username, self.smtp_password)
            logger.info("登录成功")
            
            server.sendmail(self.smtp_username, to_email, message.as_string())
            server.quit()
            
            logger.info(f"邮件发送成功: {to_email}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {to_email}, 错误: {str(e)}")
            return False
    
    def send_otp_email(self, to_email: str, otp_code: str, expires_minutes: int = 5) -> bool:
        """
        发送验证码邮件（带精美HTML模板）
        
        Args:
            to_email: 收件人邮箱
            otp_code: 验证码
            expires_minutes: 过期时间（分钟）
            
        Returns:
            bool: 发送成功返回True，失败返回False
        """
        subject = "Stellarmind 验证码"
        
        # 纯文本版本
        text_body = f"""您的验证码是: {otp_code}
        
验证码有效期为 {expires_minutes} 分钟，请尽快使用。

如果这不是您本人的操作，请忽略此邮件。

此邮件由系统自动发送，请勿回复。

---
Stellarmind 团队
"""
        
        # HTML版本
        html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>验证码</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif; background-color: #f5f7fa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f7fa; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); overflow: hidden;">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">Stellarmind</h1>
                            <p style="margin: 10px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">您的智能知识助手</p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #1f2937; font-size: 24px; font-weight: 600;">验证码</h2>
                            <p style="margin: 0 0 30px 0; color: #6b7280; font-size: 15px; line-height: 1.6;">您正在进行身份验证，您的验证码是：</p>
                            
                            <!-- OTP Box -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; padding: 20px 40px; display: inline-block;">
                                            <span style="color: #ffffff; font-size: 36px; font-weight: 700; letter-spacing: 8px; font-family: 'Courier New', monospace;">{otp_code}</span>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 30px 0 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                ⏰ 验证码有效期为 <strong style="color: #667eea;">{expires_minutes} 分钟</strong>，请尽快使用。
                            </p>
                            
                            <!-- Warning Box -->
                            <div style="margin-top: 30px; padding: 15px 20px; background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                                <p style="margin: 0; color: #92400e; font-size: 13px; line-height: 1.5;">
                                    ⚠️ <strong>安全提示：</strong>如果这不是您本人的操作，请忽略此邮件。请勿将验证码透露给任何人。
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 10px 0; color: #9ca3af; font-size: 12px;">此邮件由系统自动发送，请勿直接回复</p>
                            <p style="margin: 0; color: #9ca3af; font-size: 12px;">© 2024 Stellarmind. All rights reserved.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, text_body, html_body)


# 全局邮件服务实例
_email_service = None


def get_email_service() -> EmailService:
    """获取邮件服务实例（单例模式）"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service