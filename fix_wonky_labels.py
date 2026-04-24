"""
Batch fix for floating labels wonky logic.
Removes `-translate-x-4` from the Alpine.js dynamic class expression
so the floating label goes straight up and aligns with the text, instead
of moving left and overlapping the SVG icon.
"""
import os

TEMPLATES_DIR = r"d:\Exodus\attendance_system_master\templates\frontend"
REG_DIR = r"d:\Exodus\attendance_system_master\templates\registration"

AUTH_FILES = [
    os.path.join(TEMPLATES_DIR, 'login.html'),
    os.path.join(TEMPLATES_DIR, 'register.html'),
    os.path.join(REG_DIR, 'password_reset.html'),
    os.path.join(REG_DIR, 'password_reset_done.html'),
    os.path.join(REG_DIR, 'password_reset_confirm.html'),
    os.path.join(REG_DIR, 'password_reset_complete.html'),
]

for filepath in AUTH_FILES:
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The wonky logic causing overlap: `-translate-x-4`
    fixed_content = content.replace('-translate-y-8 -translate-x-4', '-translate-y-8')
    
    if fixed_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print(f"Fixed wonky floating label in {os.path.basename(filepath)}")
