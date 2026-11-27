import {
  AlignmentType,
  Document,
  HeadingLevel,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from 'docx';
import { buildReportDoc, type ReportBlock, type ReportInput } from './report';

const HEADINGS = {
  1: HeadingLevel.HEADING_1,
  2: HeadingLevel.HEADING_2,
  3: HeadingLevel.HEADING_3,
  4: HeadingLevel.HEADING_4,
} as const;

const MONO = 'Courier New';

function cell(text: string, right: boolean, bold: boolean): TableCell {
  return new TableCell({
    children: [
      new Paragraph({
        alignment: right ? AlignmentType.RIGHT : AlignmentType.LEFT,
        children: [new TextRun({ text, bold, size: 18 })],
      }),
    ],
  });
}

function toDocx(b: ReportBlock): (Paragraph | Table)[] {
  switch (b.t) {
    case 'h':
      return [new Paragraph({ heading: HEADINGS[b.level], children: [new TextRun(b.text)] })];
    case 'p':
      return [
        new Paragraph({
          spacing: { after: 120 },
          children: [
            ...(b.boldLead ? [new TextRun({ text: b.boldLead, bold: true })] : []),
            new TextRun(b.text),
          ],
        }),
      ];
    case 'ul':
      return b.items.map((i) => new Paragraph({ bullet: { level: 0 }, children: [new TextRun(i)] }));
    case 'code':
      return b.text.split('\n').map(
        (line) =>
          new Paragraph({ children: [new TextRun({ text: line, font: MONO, size: 18 })] }),
      );
    case 'table':
      return [
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [
            new TableRow({ tableHeader: true, children: b.head.map((t, i) => cell(t, b.right.includes(i), true)) }),
            ...b.rows.map((r) => new TableRow({ children: r.map((t, i) => cell(t, b.right.includes(i), false)) })),
          ],
        }),
        new Paragraph({ children: [] }),
      ];
  }
}

/** The report as a Word (.docx) file. */
export function reportDocx(r: ReportInput): Promise<Blob> {
  const doc = new Document({
    creator: 'Cropland Conversion Dashboard',
    title: 'Cropland conversion summary',
    sections: [{ children: buildReportDoc(r).flatMap(toDocx) }],
  });
  return Packer.toBlob(doc);
}
