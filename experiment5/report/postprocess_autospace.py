"""关闭 Word 的中西文/中文与数字自动加空格特性：向 document.xml 的每个 pPr
注入 autoSpaceDE=0 与 autoSpaceDN=0（必须位于 w:spacing 之前以满足 OOXML 顺序）。"""
import re
import shutil
import sys
import zipfile

path = sys.argv[1]
tmp = path + ".autospace.tmp"

with zipfile.ZipFile(path, "r") as zin:
    names = zin.namelist()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in names:
            data = zin.read(name)
            if name == "word/document.xml":
                xml = data.decode("utf-8")
                before = xml.count("<w:autoSpaceDE")
                xml = xml.replace(
                    "<w:spacing ",
                    '<w:autoSpaceDE w:val="0"/><w:autoSpaceDN w:val="0"/><w:spacing ',
                )
                print(f"autoSpace 注入段落元素: {xml.count('<w:autoSpaceDE') - before} 处（原有 {before}）")
                data = xml.encode("utf-8")
            zout.writestr(name, data)

shutil.move(tmp, path)
print("完成:", path)
