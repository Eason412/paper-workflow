local metadata_title = ""
local title_removed = false
local in_references = false

local function normalize(text)
  return text:gsub("^%s+", ""):gsub("%s+$", ""):gsub("%s+", " "):gsub("：$", ""):gsub(":$", "")
end

local function citation_parts(text)
  local output = pandoc.Inlines({})
  local position = 1
  while position <= #text do
    local first, last, marker = text:find("%[([%d,%-]+)%]", position)
    if not first then
      output:insert(pandoc.Str(text:sub(position)))
      break
    end
    if first > position then
      output:insert(pandoc.Str(text:sub(position, first - 1)))
    end
    output:insert(pandoc.RawInline("latex", "\\textsupcite{" .. marker .. "}"))
    position = last + 1
  end
  return output
end

local function transform_inlines(inlines)
  local output = pandoc.Inlines({})
  for _, inline in ipairs(inlines) do
    if inline.tag == "Str" and inline.text:match("%[[%d,%-]+%]") then
      output:extend(citation_parts(inline.text))
    elseif inline.tag == "Math" and inline.mathtype == "DisplayMath" then
      local math = inline.text:gsub("^%s+", ""):gsub("%s+$", "")
      if math ~= "" and not math:find("\\begin{", 1, true) and not math:find("\\tag{", 1, true) and not math:find("\\label{", 1, true) then
        output:insert(pandoc.RawInline("latex", "\\begin{equation}\n" .. math .. "\n\\end{equation}"))
      else
        output:insert(inline)
      end
    elseif inline.tag == "Link" or inline.tag == "Image" or inline.tag == "Code" or inline.tag == "RawInline" or inline.tag == "Note" then
      output:insert(inline)
    elseif inline.content then
      inline.content = transform_inlines(inline.content)
      output:insert(inline)
    else
      output:insert(inline)
    end
  end
  return output
end

local transform_blocks

local function transform_block(block)
  if block.tag == "Header" then
    local heading_text = normalize(pandoc.utils.stringify(block.content))
    local heading_key = heading_text:lower()

    if heading_text == "参考文献" or heading_key == "references" or heading_key == "reference" then
      in_references = true
      return pandoc.RawBlock(
        "latex",
        "% COURSE_REPORT_REFERENCES_BEGIN\n\\phantomsection\n\\section*{\\centering\\zihao{3}\\songti\\bfseries 参考文献}\n\\addcontentsline{toc}{section}{参考文献}"
      )
    end

    if not title_removed and block.level == 1 and heading_text == metadata_title then
      title_removed = true
      return nil
    end

    if block.level > 1 then
      block.level = block.level - 1
    end
    return block
  end

  if not in_references and (block.tag == "Para" or block.tag == "Plain") then
    block.content = transform_inlines(block.content)
    return block
  end

  if block.tag == "BlockQuote" or block.tag == "Div" then
    block.content = transform_blocks(block.content)
  elseif block.tag == "BulletList" then
    for index, item in ipairs(block.content) do
      block.content[index] = transform_blocks(item)
    end
  elseif block.tag == "OrderedList" then
    for index, item in ipairs(block.content[2]) do
      block.content[2][index] = transform_blocks(item)
    end
  elseif block.tag == "DefinitionList" then
    for _, item in ipairs(block.content) do
      for index, definition in ipairs(item[2]) do
        item[2][index] = transform_blocks(definition)
      end
    end
  end
  return block
end

transform_blocks = function(blocks)
  local output = pandoc.Blocks({})
  for _, block in ipairs(blocks) do
    local transformed = transform_block(block)
    if transformed then
      output:insert(transformed)
    end
  end
  return output
end

function Pandoc(doc)
  if doc.meta.title then
    metadata_title = normalize(pandoc.utils.stringify(doc.meta.title))
  end
  doc.blocks = transform_blocks(doc.blocks)
  return doc
end
