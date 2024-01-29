# IPython/Jupyter setup (Optional: edit or remove at your wish)
%reload_ext autoreload
%autoreload 2
from IPython.display import display, HTML, Markdown
# make wide HTML cells (e.g., as created by `display(dataframe)`) display a scrollbar:
display(HTML("<style>div.jp-OutputArea-output.jp-RenderedHTML{display:block;overflow:auto;}</style>"))
from IPython.core.display import HTML
# make tables cells with a border:
display(HTML("<style>th, td{border: 1px solid #DDE !important;}</style>"))