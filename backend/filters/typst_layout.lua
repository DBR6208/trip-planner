-- Translate neutral brochure layout divs into Typst blocks.

function Div(el)
  if el.classes:includes("page-break") then
    return pandoc.RawBlock("typst", "#pagebreak()")
  end

  if el.classes:includes("restaurant-card") then
    local blocks = pandoc.Blocks({
      pandoc.RawBlock("typst", "#block(breakable: false)["),
    })
    blocks:extend(el.content)
    blocks:insert(pandoc.RawBlock("typst", "]"))
    return blocks
  end
end