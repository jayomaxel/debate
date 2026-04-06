"""
邮件发送服务
负责发送辩论报告邮件
"""

import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from sqlalchemy.orm import Session
from config import settings
from logging_config import get_logger
from services.config_service import ConfigService

logger = get_logger(__name__)


class EmailService:
    """邮件服务"""

    @staticmethod
    async def send_report_email(
        db: Session,
        to_email: str,
        student_name: str,
        debate_topic: str,
        report_summary: str,
        attachment_data: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        """
        发送报告邮件

        Args:
            db: 数据库会话
            to_email: 收件人邮箱
            student_name: 学生姓名
            debate_topic: 辩题
            report_summary: 报告摘要
            attachment_data: 附件数据（可选）
            attachment_filename: 附件文件名（可选）

        Returns:
            是否发送成功
        """
        try:
            config_service = ConfigService(db)
            email_config = await config_service.get_email_config()

            smtp_user = (
                email_config.smtp_user or email_config.from_email or ""
            ).strip()
            smtp_password = (email_config.smtp_password or "").strip()

            # 检查SMTP配置
            if not smtp_user or not smtp_password:
                logger.error("SMTP配置未设置")
                return False

            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = email_config.from_email or smtp_user
            msg["To"] = to_email
            msg["Subject"] = f"辩论报告 - {debate_topic}"

            # 邮件正文
            body = f"""
尊敬的{student_name}同学：

您好！

您参与的辩论"{debate_topic}"已经结束，以下是辩论报告内容：

{report_summary}

如需导出PDF，请登录系统在辩论报告页面导出。

祝您学习进步！

---
辩论教学系统
{settings.APP_NAME}
"""

            msg.attach(MIMEText(body, "plain", "utf-8"))

            # 添加附件
            if attachment_data and attachment_filename:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment_data)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {attachment_filename}",
                )
                msg.attach(part)
                try:
                    logger.info(
                        f"已添加附件: name={attachment_filename} "
                        f"size={len(attachment_data)}B"
                    )
                except Exception:
                    logger.info(f"已添加附件: name={attachment_filename}")

            logger.info(
                f"SMTP账号信息: user={smtp_user} pwd_len={len(smtp_password)}"
            )
            use_ssl = (email_config.smtp_port or 0) == 465
            logger.info(
                f"准备连接SMTP: host={email_config.smtp_host} "
                f"port={email_config.smtp_port} ssl={use_ssl}"
            )
            start_time = time.time()
            smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
            with smtp_cls(
                email_config.smtp_host,
                email_config.smtp_port,
                timeout=10,
            ) as server:
                try:
                    server.login(
                        smtp_user,
                        smtp_password,
                    )
                    logger.info(
                        f"SMTP认证成功: user={smtp_user}"
                    )
                except smtplib.SMTPAuthenticationError as ae:
                    try:
                        logger.error(
                            f"SMTP认证失败: code={ae.smtp_code} "
                            f"msg={ae.smtp_error}",
                            exc_info=True,
                        )
                    except Exception:
                        logger.error(f"SMTP认证失败: {ae}", exc_info=True)
                    return False
                refused = server.send_message(msg)
                elapsed_ms = int((time.time() - start_time) * 1000)
                if refused:
                    logger.error(
                        f"收件人被拒绝: refused={refused} 耗时={elapsed_ms}ms"
                    )
                    return False
                logger.info(
                    f"报告邮件发送成功: to={to_email} 耗时={elapsed_ms}ms"
                )
            return True

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"连接被服务器意外关闭: msg={e}", exc_info=True)
            return False
        except smtplib.SMTPConnectError as e:
            try:
                code = getattr(e, "smtp_code", None)
                msg = getattr(e, "smtp_error", None)
                logger.error(
                    f"SMTP连接失败: code={code} msg={msg}",
                    exc_info=True,
                )
            except Exception:
                logger.error(f"SMTP连接失败: {e}", exc_info=True)
            return False
        except smtplib.SMTPDataError as e:
            try:
                logger.error(
                    f"SMTP数据错误: code={e.smtp_code} msg={e.smtp_error}",
                    exc_info=True,
                )
            except Exception:
                logger.error(f"SMTP数据错误: {e}", exc_info=True)
            return False
        except smtplib.SMTPSenderRefused as e:
            try:
                logger.error(
                    f"发件人被拒绝: sender={e.sender} "
                    f"code={e.smtp_code} msg={e.smtp_error}",
                    exc_info=True,
                )
            except Exception:
                logger.error(f"发件人被拒绝: {e}", exc_info=True)
            return False
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(
                f"收件人被拒绝: refused={getattr(e, 'recipients', {})}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(f"发送邮件失败: {e}", exc_info=True)
            return False

    @staticmethod
    async def send_class_report_email(
        db: Session,
        to_email: str,
        teacher_name: str,
        class_name: str,
        report_summary: str,
        attachment_data: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        """
        发送班级报告邮件

        Args:
            db: 数据库会话
            to_email: 收件人邮箱
            teacher_name: 教师姓名
            class_name: 班级名称
            report_summary: 报告摘要
            attachment_data: 附件数据（可选）
            attachment_filename: 附件文件名（可选）

        Returns:
            是否发送成功
        """
        try:
            config_service = ConfigService(db)
            email_config = await config_service.get_email_config()

            smtp_user = (
                email_config.smtp_user or email_config.from_email or ""
            ).strip()
            smtp_password = (email_config.smtp_password or "").strip()

            # 检查SMTP配置
            if not smtp_user or not smtp_password:
                logger.error("SMTP配置未设置")
                return False

            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = email_config.from_email or smtp_user
            msg["To"] = to_email
            msg["Subject"] = f"班级辩论报告 - {class_name}"

            # 邮件正文
            body = f"""
尊敬的{teacher_name}老师：

您好！

{class_name}的辩论活动报告已生成，以下是报告摘要：

{report_summary}

详细报告请查看附件。

---
辩论教学系统
{settings.APP_NAME}
"""

            msg.attach(MIMEText(body, "plain", "utf-8"))

            # 添加附件
            if attachment_data and attachment_filename:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment_data)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {attachment_filename}",
                )
                msg.attach(part)
                try:
                    logger.info(
                        f"已添加附件: name={attachment_filename} "
                        f"size={len(attachment_data)}B"
                    )
                except Exception:
                    logger.info(f"已添加附件: name={attachment_filename}")

            logger.info(
                f"SMTP账号信息: user={smtp_user} pwd_len={len(smtp_password)}"
            )
            use_ssl = (email_config.smtp_port or 0) == 465
            logger.info(
                f"准备连接SMTP: host={email_config.smtp_host} "
                f"port={email_config.smtp_port} ssl={use_ssl}"
            )
            start_time = time.time()
            smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
            with smtp_cls(
                email_config.smtp_host,
                email_config.smtp_port,
                timeout=10,
            ) as server:
                try:
                    server.set_debuglevel(1 if settings.DEBUG else 0)
                except Exception:
                    pass
                try:
                    ehlo_code, ehlo_msg = server.ehlo()
                    logger.info(
                        f"EHLO响应: code={ehlo_code} msg={ehlo_msg}"
                    )
                except Exception as e_ehlo:
                    logger.warning(f"EHLO失败: {e_ehlo}")
                if not use_ssl:
                    try:
                        if server.has_extn("starttls"):
                            logger.info("服务器支持STARTTLS，开始TLS握手")
                            server.starttls()
                            try:
                                tls_ehlo_code, tls_ehlo_msg = server.ehlo()
                                logger.info(
                                    f"TLS后EHLO响应: code={tls_ehlo_code} "
                                    f"msg={tls_ehlo_msg}"
                                )
                            except Exception as e_tls_ehlo:
                                logger.warning(f"TLS后EHLO失败: {e_tls_ehlo}")
                        else:
                            logger.warning("服务器不支持STARTTLS")
                    except smtplib.SMTPException as e_tls:
                        logger.error(f"TLS握手失败: {e_tls}", exc_info=True)
                        return False
                try:
                    server.login(
                        smtp_user,
                        smtp_password,
                    )
                    logger.info(
                        f"SMTP认证成功: user={smtp_user}"
                    )
                except smtplib.SMTPAuthenticationError as ae:
                    try:
                        logger.error(
                            f"SMTP认证失败: code={ae.smtp_code} "
                            f"msg={ae.smtp_error}",
                            exc_info=True,
                        )
                    except Exception:
                        logger.error(f"SMTP认证失败: {ae}", exc_info=True)
                    return False
                refused = server.send_message(msg)
                elapsed_ms = int((time.time() - start_time) * 1000)
                if refused:
                    logger.error(
                        f"收件人被拒绝: refused={refused} 耗时={elapsed_ms}ms"
                    )
                    return False
                logger.info(
                    f"班级报告邮件发送成功: to={to_email} 耗时={elapsed_ms}ms"
                )
            return True

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"连接被服务器意外关闭: msg={e}", exc_info=True)
            return False
        except smtplib.SMTPConnectError as e:
            try:
                code = getattr(e, "smtp_code", None)
                msg = getattr(e, "smtp_error", None)
                logger.error(
                    f"SMTP连接失败: code={code} msg={msg}",
                    exc_info=True,
                )
            except Exception:
                logger.error(f"SMTP连接失败: {e}", exc_info=True)
            return False
        except smtplib.SMTPDataError as e:
            try:
                logger.error(
                    f"SMTP数据错误: code={e.smtp_code} msg={e.smtp_error}",
                    exc_info=True,
                )
            except Exception:
                logger.error(f"SMTP数据错误: {e}", exc_info=True)
            return False
        except smtplib.SMTPSenderRefused as e:
            try:
                logger.error(
                    f"发件人被拒绝: sender={e.sender} "
                    f"code={e.smtp_code} msg={e.smtp_error}",
                    exc_info=True,
                )
            except Exception:
                logger.error(f"发件人被拒绝: {e}", exc_info=True)
            return False
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(
                f"收件人被拒绝: refused={getattr(e, 'recipients', {})}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(f"发送邮件失败: {e}", exc_info=True)
            return False

    @staticmethod
    async def test_email_connection(db: Session) -> tuple[bool, Optional[str]]:
        """
        测试邮件连接

        Returns:
            (是否成功, 错误信息)
        """
        try:
            config_service = ConfigService(db)
            email_config = await config_service.get_email_config()

            smtp_user = (
                email_config.smtp_user or email_config.from_email or ""
            ).strip()
            smtp_password = (email_config.smtp_password or "").strip()

            if not smtp_user or not smtp_password:
                return False, "SMTP配置未设置"

            use_ssl = (email_config.smtp_port or 0) == 465
            smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
            with smtp_cls(
                email_config.smtp_host, email_config.smtp_port, timeout=10
            ) as server:
                try:
                    server.set_debuglevel(1 if settings.DEBUG else 0)
                except Exception:
                    pass
                try:
                    ehlo_code, ehlo_msg = server.ehlo()
                    logger.info(
                        f"EHLO响应: code={ehlo_code} msg={ehlo_msg}"
                    )
                except Exception as e_ehlo:
                    logger.warning(f"EHLO失败: {e_ehlo}")
                if not use_ssl:
                    if server.has_extn("starttls"):
                        logger.info("服务器支持STARTTLS，开始TLS握手")
                        server.starttls()
                        try:
                            tls_ehlo_code, tls_ehlo_msg = server.ehlo()
                            logger.info(
                                f"TLS后EHLO响应: code={tls_ehlo_code} "
                                f"msg={tls_ehlo_msg}"
                            )
                        except Exception as e_tls_ehlo:
                            logger.warning(f"TLS后EHLO失败: {e_tls_ehlo}")
                    else:
                        logger.warning("服务器不支持STARTTLS")
                server.login(
                    smtp_user,
                    smtp_password,
                )

            logger.info("邮件连接测试成功")
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"邮件连接测试失败: {error_msg}")
            return False, error_msg
