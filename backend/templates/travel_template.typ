#let travel-blue = rgb("003366")
#let travel-gold = rgb("A07F40")
#let travel-accent = rgb("D4A84B")
#let table-alt = rgb("F3F1ED")

#let conf(
  title: none,
  date: none,
  citytitle: none,
  logo: none,
  cover-image: none,
  doc,
  ..args
) = {
  set document(title: title)
  set text(font: "Times New Roman", size: 11pt)
  set par(first-line-indent: 0pt, leading: 1.0em, spacing: 0.85em, justify: false)
  set page(
    paper: "a4",
    margin: 1in,
    header: [
      #align(right)[#text(size: 8pt, fill: travel-blue)[#title]]
      #v(2pt)
      #line(length: 100%, stroke: 1.2pt + travel-gold)
    ],
    footer: align(center)[#context counter(page).display("1")],
  )
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => block(above: 1.65em, below: 1.0em)[
    #text(size: 17pt, weight: "bold", fill: travel-blue)[#it]
  ]
  show heading.where(level: 2): it => block(above: 1.45em, below: 1.0em)[
    #text(size: 13pt, weight: "bold", fill: travel-blue)[#it]
  ]
  show heading.where(level: 3): it => block(above: 1.0em, below: 0.65em)[
    #text(size: 11pt, weight: "bold", fill: travel-blue)[#it]
  ]
  show figure.where(kind: image): it => align(center)[it]
  show table: it => {
    set table(stroke: none, inset: 6pt)
    it
  }

  set page(header: none, footer: none)
  align(center)[
    #if logo != none [
      #grid(
        columns: (auto, auto),
        column-gutter: 0.5em,
        align: center,
        [#image(logo, width: 52pt)],
        [
          #text(size: 28pt, weight: "bold", fill: travel-blue)[DBG ]
          #text(size: 28pt, weight: "bold", fill: travel-gold)[TRAVEL]
        ],
      )
    ] else [
      #text(size: 28pt, weight: "bold", fill: travel-blue)[DBG ]
      #text(size: 28pt, weight: "bold", fill: travel-gold)[TRAVEL]
    ]
    #v(8.5pt)
    #line(length: 40%, stroke: 1.5pt + travel-accent)
    #v(14pt)
    #if cover-image != none [
      #image(cover-image, width: 100%, height: 30%, fit: "contain")
      #v(14pt)
    ] else [
      #v(42.5pt)
    ]
    #text(size: 28pt, weight: "bold", fill: travel-blue)[#citytitle]
    #v(42.5pt)
    #text(size: 15pt)[#date]
    #v(1fr)
  ]

  pagebreak()
  set page(
    header: [
      #align(right)[#text(size: 8pt, fill: travel-blue)[#title]]
      #v(2pt)
      #line(length: 100%, stroke: 1.2pt + travel-gold)
    ],
    footer: align(center)[#context counter(page).display("1")],
  )
  outline(title: [Contents], depth: 2)
  pagebreak()
  doc
}

#show: doc => conf(
$if(title)$
  title: [$title$],
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(citytitle)$
  citytitle: [$citytitle$],
$endif$
$if(logo)$
  logo: "$logo$",
$endif$
$if(cover-image)$
  cover-image: "$cover-image$",
$endif$
  doc,
)

$body$