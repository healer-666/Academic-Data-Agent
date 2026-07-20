import { toAbsoluteFileUrl } from "../api";

function InlineMarkdown({ text }) {
  const source = String(text ?? "");
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  const parts = source.split(pattern).filter((part) => part !== "");
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("`") && part.endsWith("`")) {
          return <code key={`${part}-${index}`}>{part.slice(1, -1)}</code>;
        }
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
        }
        const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        if (link) {
          return (
            <a key={`${part}-${index}`} href={toAbsoluteFileUrl(link[2])} target="_blank" rel="noreferrer">
              {link[1]}
            </a>
          );
        }
        return <span key={`${part}-${index}`}>{part}</span>;
      })}
    </>
  );
}

function MarkdownView({ content }) {
  const lines = String(content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (/^```/.test(line.trim())) {
      const language = line.trim().replace(/^```/, "").trim();
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^```/.test(lines[index].trim())) {
        codeLines.push(lines[index]);
        index += 1;
      }
      index += index < lines.length ? 1 : 0;
      blocks.push(
        <pre key={`code-${blocks.length}`} data-language={language || undefined}>
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    const imageMatch = line.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (imageMatch) {
      blocks.push(
        <figure key={`image-${blocks.length}`} className="markdown-figure">
          <img src={toAbsoluteFileUrl(imageMatch[2])} alt={imageMatch[1] || "图表"} />
          {imageMatch[1] && <figcaption>{imageMatch[1]}</figcaption>}
        </figure>,
      );
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      const Heading = `h${Math.min(heading[1].length + 1, 4)}`;
      blocks.push(<Heading key={`heading-${blocks.length}`}><InlineMarkdown text={heading[2]} /></Heading>);
      index += 1;
      continue;
    }

    if (line.includes("|") && /^\s*\|?\s*:?-{3,}:?/.test(lines[index + 1] || "")) {
      const splitRow = (value) =>
        value
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((cell) => cell.trim());
      const headers = splitRow(line);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        rows.push(splitRow(lines[index]));
        index += 1;
      }
      blocks.push(
        <div className="markdown-table-wrap" key={`table-${blocks.length}`}>
          <table>
            <thead>
              <tr>{headers.map((header) => <th key={header}><InlineMarkdown text={header} /></th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {headers.map((_, cellIndex) => (
                    <td key={cellIndex}><InlineMarkdown text={row[cellIndex] || ""} /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (/^\s*(?:[-*+]\s+|\d+[.)]\s+)/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items = [];
      while (index < lines.length && /^\s*(?:[-*+]\s+|\d+[.)]\s+)/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+)/, ""));
        index += 1;
      }
      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List key={`list-${blocks.length}`}>
          {items.map((item, itemIndex) => (
            <li key={itemIndex}><InlineMarkdown text={item} /></li>
          ))}
        </List>,
      );
      continue;
    }

    const paragraph = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^```/.test(lines[index].trim()) &&
      !/^(#{1,4})\s+/.test(lines[index]) &&
      !/^\s*(?:[-*+]\s+|\d+[.)]\s+)/.test(lines[index])
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push(
      <p key={`p-${blocks.length}`}>
        {paragraph.map((item, itemIndex) => (
          <span key={itemIndex}>
            {itemIndex > 0 && <br />}
            <InlineMarkdown text={item} />
          </span>
        ))}
      </p>,
    );
  }

  return <div className="markdown-view">{blocks}</div>;
}

export default MarkdownView;
