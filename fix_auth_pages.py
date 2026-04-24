"""
Batch fix for auth pages to:
1. Add the dark mode theme synchronization script (to respect localStorage).
2. Fix "squeezed" mobile padding on cards (p-8 -> p-6 on mobile).
"""
import os
import re

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

THEME_SCRIPT = """
    <!-- Dark mode sync -->
    <script>
      (function () {
        var html = document.documentElement;
        var stored = localStorage.getItem('exodus-theme');
        var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (stored === 'dark' || (!stored && prefersDark)) {
          html.classList.add('dark');
        } else {
          html.classList.remove('dark');
        }
      })();
    </script>
  </head>"""

for filepath in AUTH_FILES:
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Inject theme script before </head> if not already there
    if 'localStorage.getItem(\'exodus-theme\')' not in content:
        content = content.replace('</head>', THEME_SCRIPT)

    # 2. Fix squeezed mobile layout
    # Change padding p-8 to p-6 for small screens to give more room to inputs
    content = content.replace('p-8 sm:p-10', 'p-6 sm:p-10')
    content = content.replace('p-8', 'p-6 sm:p-8') # Just in case
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Auth pages updated with theme sync and mobile layout fixes.")
