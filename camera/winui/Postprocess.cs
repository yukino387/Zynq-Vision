namespace CNNStudio;

public record Detection(int ClassId, double Score, double X1, double Y1, double X2, double Y2)
{
    public string Label => Postprocess.Labels[ClassId];
    public string Confidence => $"{Score:P0}";
}
public static class Postprocess
{
    public static readonly string[] Labels = ["龟裂", "夹杂", "斑块", "麻点", "轧入氧化皮", "划痕"];
    private static readonly double[][] Anchors = [[1.3629538461538462, 1.3798076923076923,
        2.2716615384615384, 2.843723076923077, 5.788461538461538, 5.367815384615384],
        [0.7740384615384615, 0.9086538461538461, 1.2451923076923077, 1.9519230769230769,
        2.7259615384615383, 2.7596153846153846]];
    private static double Sigmoid(double value) => 1 / (1 + Math.Exp(-value));
    public static List<Detection> Detect(byte[] out0, byte[] out1, double confidence, double iou)
    {
        List<Detection> candidates = [];
        Decode(out0, 7, 0.11581249687615341, Anchors[0], confidence, candidates);
        Decode(out1, 14, 0.15977688286248154, Anchors[1], confidence, candidates);
        List<Detection> kept = [];
        foreach (var group in candidates.GroupBy(x => x.ClassId))
        {
            var remaining = group.OrderByDescending(x => x.Score).ToList();
            while (remaining.Count > 0)
            {
                var best = remaining[0];
                kept.Add(best);
                remaining = remaining.Skip(1).Where(x => Overlap(best, x) <= iou).ToList();
            }
        }
        return kept.OrderByDescending(x => x.Score).Select(x => x with {
            X1 = Math.Clamp(x.X1, 0, 416), Y1 = Math.Clamp(x.Y1, 0, 416),
            X2 = Math.Clamp(x.X2, 0, 416), Y2 = Math.Clamp(x.Y2, 0, 416) }).ToList();
    }
    private static void Decode(byte[] raw, int size, double scale, double[] anchors, double threshold, List<Detection> output)
    {
        double Value(int anchor, int channel, int cell) =>
            unchecked((sbyte)raw[(anchor * 11 + channel) * size * size + cell]) * scale;
        for (int anchor = 0; anchor < 3; anchor++)
            for (int cell = 0; cell < size * size; cell++)
            {
                double obj = Sigmoid(Value(anchor, 4, cell));
                if (obj < threshold) continue;
                int bestClass = 0;
                double bestValue = Value(anchor, 5, cell);
                for (int cls = 1; cls < Labels.Length; cls++)
                    if (Value(anchor, 5 + cls, cell) > bestValue)
                    { bestClass = cls; bestValue = Value(anchor, 5 + cls, cell); }
                double score = obj * Sigmoid(bestValue);
                if (score < threshold) continue;
                double x = (Sigmoid(Value(anchor, 0, cell)) + cell % size) * 416 / size;
                double y = (Sigmoid(Value(anchor, 1, cell)) + cell / size) * 416 / size;
                double w = Math.Exp(Value(anchor, 2, cell)) * anchors[anchor * 2] * 416 / size;
                double h = Math.Exp(Value(anchor, 3, cell)) * anchors[anchor * 2 + 1] * 416 / size;
                output.Add(new(bestClass, score, x - w / 2, y - h / 2, x + w / 2, y + h / 2));
            }
    }
    private static double Overlap(Detection a, Detection b)
    {
        double intersection = Math.Max(0, Math.Min(a.X2, b.X2) - Math.Max(a.X1, b.X1)) *
            Math.Max(0, Math.Min(a.Y2, b.Y2) - Math.Max(a.Y1, b.Y1));
        double union = (a.X2-a.X1)*(a.Y2-a.Y1) + (b.X2-b.X1)*(b.Y2-b.Y1) - intersection;
        return union > 0 ? intersection / union : 0;
    }
}
