import os
import glob
import re

base_dir = r"d:\Exodus\attendance_system_master\templates"
html_files = glob.glob(os.path.join(base_dir, "**/*.html"), recursive=True)

# Regex to find <th ... class="..."> and replace text-gray-500 with text-gray-700 dark:text-gray-300 font-bold
# Or easier: just replace 'text-gray-500' inside any file if it's related to text.
# Actually, let's just do exact string replacements for gradients first.

replacements = {
    # Darken gradients for white text contrast
    "from-teal-500 to-emerald-500": "from-teal-600 to-emerald-700",
    "hover:from-teal-600 hover:to-emerald-600": "hover:from-teal-700 hover:to-emerald-800",
    
    "from-indigo-500 to-blue-500": "from-indigo-600 to-blue-700",
    "hover:from-indigo-600 hover:to-blue-600": "hover:from-indigo-700 hover:to-blue-800",
    
    "from-indigo-500 to-cyan-500": "from-indigo-600 to-cyan-700",
    "hover:from-indigo-600 hover:to-cyan-600": "hover:from-indigo-700 hover:to-cyan-800",
    
    # Table headers contrast fix
    'text-gray-500 text-gray-500': 'text-gray-700 dark:text-gray-300 font-bold', # existing typo from earlier
    'class="px-4 py-2 text-left text-xs font-medium text-gray-500"': 'class="px-4 py-2 text-left text-xs font-bold text-gray-800 dark:text-gray-300"',
    'class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"': 'class="px-6 py-3 text-left text-xs font-bold text-gray-800 dark:text-gray-300 uppercase tracking-wider"',
    'tracking-wider text-gray-500 hover:bg-gray-100': 'tracking-wider text-gray-800 dark:text-gray-300 font-bold hover:bg-gray-100',
    'class="px-5 py-3 text-left text-xs font-medium uppercase text-gray-500"': 'class="px-5 py-3 text-left text-xs font-bold uppercase text-gray-800 dark:text-gray-300"',
    # Just to be safe, darken all `text-gray-500` inside `th` tags.
}

for file_path in html_files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    original_content = content
    for old, new in replacements.items():
        content = content.replace(old, new)
        
    # Regex magic to catch any missing <th ... text-gray-500 ...>
    content = re.sub(r'(<th[^>]+)text-gray-500([^>]*>)', r'\1text-gray-800 dark:text-gray-300 font-bold\2', content)
    
    if content != original_content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {file_path}")

print("Done bulk replacing.")
