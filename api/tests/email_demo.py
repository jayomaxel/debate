import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置信息
sender_email = "529562760@qq.com"      # 你的 QQ 邮箱（如 123456789@qq.com）
sender_password = "eysyveftzfkybiba" # 刚才获取的 16 位授权码
receiver_email = "529562760@qq.com"    # 收件人邮箱

# 创建邮件
message = MIMEMultipart("alternative")
message["Subject"] = "来自 Python 的 QQ 邮箱测试"
message["From"] = sender_email
message["To"] = receiver_email

# 邮件正文（纯文本）
text = "你好！这是一封通过 Python 使用 QQ 邮箱发送的测试邮件。"
part = MIMEText(text, "plain", "utf-8")  # 指定 utf-8 避免中文乱码
message.attach(part)

# 发送邮件
try:
    # QQ 邮箱 SMTP 服务器地址和端口（SSL 方式）
    with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())
    print("✅ 邮件发送成功！")
except Exception as e:
    print(f"❌ 邮件发送失败: {e}")