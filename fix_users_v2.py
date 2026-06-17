#!/usr/bin/env python3
"""
全面修复 users.py 中的所有语法错误
"""
import re

# 读取文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/users.py', 'r') as f:
    lines = f.readlines()

fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # 检查是否是被破坏的函数定义行
    if '# 单用户模式：不再需要用户认证' in line:
        # 找到这一行的函数定义
        if 'async def' in line or 'def ' in line:
            # 这一行是函数定义，包含了注释
            # 移除注释部分
            fixed_line = re.sub(r'# 单用户模式：不再需要用户认证.*?(req_logger = Depends\([^)]+\)):\s*"""\s*\n\s*(current_user)', 
                               r'\1:\n    """\n    \2 = {"user_id": 1, "sub": "admin"}', 
                               line + lines[i+1] + lines[i+2] + lines[i+3])
            fixed_lines.append(fixed_line)
            i += 4  # 跳过接下来的 3 行
        else:
            # 这是一个被破坏的函数定义的延续
            # 检查接下来的行
            next_line = lines[i+1] if i+1 < len(lines) else ''
            if 'req_logger = Depends' in next_line:
                # 找到函数定义的参数行
                # 移除注释并添加 current_user
                fixed_line = re.sub(r'# 单用户模式：不再需要用户认证\s*\n\s*(req_logger = Depends\([^)]+\)):', 
                                   r'\1:\n    """\n    current_user = {"user_id": 1, "sub": "admin"}', 
                                   line + next_line)
                fixed_lines.append(fixed_line)
                i += 2  # 跳过注释行和参数行
            else:
                fixed_lines.append(line)
                i += 1
    else:
        fixed_lines.append(line)
        i += 1

# 写入文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/users.py', 'w') as f:
    f.writelines(fixed_lines)

print("users.py 全面修复完成")
