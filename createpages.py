import os
from shutil import copyfile
import datetime
# Get the list of JSON files inside static/plotly directory
json_files = [f for f in os.listdir('static/plotly') if f.endswith('.json')]

# Loop to create pages
for json_file in json_files:
    # Extract the filename without extension
    filename = os.path.splitext(json_file)[0]
    filename = filename.capitalize()
    page_file = f'content/posts/{filename}.md'

    # Add title, subtitle, and content to the Markdown file
    page_title = f'{filename}'
    page_subtitle = f'Come si dice {filename}?'
    page_content = f'{{{{< load-plotly >}}}}\n{{{{< plotly json="/plotly/{json_file}" >}}}}'

    with open(page_file, 'w') as f:
        f.write(f'---\ntitle: "{page_title}"\n---\n\n## {page_subtitle}\n\n{page_content}')
