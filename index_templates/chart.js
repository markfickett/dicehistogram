<%text>
var MARGIN = {top: 30, right: 30, bottom: 50, left: 50};
var LEGEND_WIDTH = 200;
var HEIGHT = 300 - (MARGIN.top + MARGIN.bottom);
d3.selectAll('.chart').attr('height', HEIGHT + 'px');

Object.keys(g_chartConfigs)
  .forEach(extractChartDetails);

/**
 * Looks up the <svg> to render into in the DOM, and chart data from
 * g_chartConfigs and g_chartData written by the index.mako template.
 */
function extractChartDetails(chartId, unused_i, unused_keys) {
  // Chart container, including space for axes and title.
  var container = d3.select(`#${chartId}`);
  if (container.size() <= 0) {
    console.log(`No chart ${chartId} found in DOM, skipping.`);
    return;
  }
  var chartDetails = g_chartConfigs[chartId];
  var srcs = chartDetails.filenames.map(function(filename) {
    return g_chartData[filename];
  });
  var srcNames = null;
  if (chartDetails.names) {
    if (chartDetails.names.length == srcs.length) {
    } else {
      console.log(
          `Length mismatch: ${srcs.length} srcs, `
          `${chartDetails.names.length} names.`);
    }
    srcNames = chartDetails.names;
  }
  var title = chartDetails.title;

  renderChart(container, title, srcs, srcNames, chartDetails.fairValue);
}

/**
 * Renders one die fairness histogram with error bars.
 *
 * @param container: The SVG DOM element to render into.
 * @parameter title: String title for the chart.
 * @param srcs: List of histograms of die roll data to display. Each histogram
 *     is a list of objects with:
 *         side: Numeric value of the die side rolled.
 *         p: Float probability the side appeared.
 *         ci_high: 95% confidence interval high value.
 *         ci_low: 95% confidence interval low value.
 * @param srcNames: List of string names to display as a legend for the sources,
 *     or null if no legend is to be shown.
 * @param fairValueOverride: An explicitly specified fair value for the chart,
 *     or null if (1 / srcs.length) is the fair value.
 */
function renderChart(container, title, srcs, srcNames, fairValueOverride) {
  // SVG renders in a top-left coordinate system, so Y values increase downard.

  console.log(`Rendering ${title}.`);
  var numSides = srcs[0].length;

  var barMargin = 3;
  var barWidth = 12;
  var sideGroupWidth = barWidth + barMargin;
  if (srcs.length > 1) {
    barMargin = 1;
    if (srcs.length > 4) {
      barWidth = 6;
    }
    sideGroupWidth = (srcs.length + 2) * (barMargin + barWidth);
  }

  var yScale = d3.scaleLinear()
      .range([HEIGHT, 0]);
  var xScale = d3.scaleBand();

  var xAxis = d3.axisBottom(xScale);
  var yAxis = d3.axisLeft(yScale);

  var chartWidth = numSides * sideGroupWidth;
  var containerWidth = chartWidth + MARGIN.left + MARGIN.right;
  if (srcNames) {
    containerWidth += LEGEND_WIDTH;
  }
  xScale
      .domain(srcs[0].map(function(d) { return d.side; }))
      .range([0, chartWidth]);

  var fairValue = fairValueOverride || 1.0 / numSides;
  var zippedData = [];
  for(var s = 0; s < numSides; s++) {
    var zippedValue = {side: s + 1, values: []};
    for(var i = 0; i < srcs.length; i++) {
      zippedValue.values.push(srcs[i][s]);
    }
    zippedData.push(zippedValue);
  }
  var maxValue = d3.max(srcs, function(src) {
      return d3.max(src, function(d) { return d.ci_high; })
  });
  yScale.domain([0.0, maxValue]);
  yAxis.tickSizeInner(-chartWidth);

  container
      .attr("width", containerWidth)
      .attr("height", HEIGHT + MARGIN.top + MARGIN.bottom);
  container.append("text")
      .attr("class", "title")
      .attr("x", (MARGIN.left + chartWidth) / 2)
      .attr("y", 20)
      .style("text-anchor", "middle")
      .text(title);

  var chart = container.append("g")
      .attr("transform", `translate(${MARGIN.left}, ${MARGIN.top})`);

  // Y axis, and "fair" line at even probability
  chart.append("g")
      .attr("class", "y axis")
      .attr("transform", `translate(-2, 0)`)
      .call(yAxis)
      .append("text")
          .attr("transform", "rotate(-90)")
          .attr("y", -45)
          .attr("x", -yScale(maxValue / 2))
          .attr("dy", "0.71em")
          .style("text-anchor", "middle")
          .text(`Frequency (fair = ${fairValue.toFixed(2)})`);
  chart.append("line")
      .attr("class", "fair")
      .attr("x1", 0)
      .attr("x2", chartWidth)
      .attr("y1", yScale(fairValue))
      .attr("y2", yScale(fairValue))
      .attr("width", chartWidth);

  // X axis
  chart.append("g")
      .attr("class", "x axis")
      .attr("transform", `translate(0, ${HEIGHT + 1})`)
      .call(xAxis)
      .append("text")
          .text("Die Side Rolled")
          .attr("x", chartWidth / 2)
          .attr("y", 29)
          .style("text-anchor", "middle");

  // one group for each of the die's sides
  var sideGroup = chart.selectAll("g.side-group")
      .data(zippedData)
      .enter().append("g")
          .attr("class", "side-group")
          .attr("transform", function(d, i) {
              return "translate(" +
                  (xScale(+d.side) + 2 * barMargin) +
                  ", 0)";
          });
  // bar containers within each side group; one bar per side for single-die
  // graphs, or multiple bars for multiple dice / sample sizes etc
  var bar = sideGroup.selectAll("g")
      .data(function(d, i) { return d.values; })
      .enter().append("g")
          .attr("width", barWidth)
          .attr("height", HEIGHT)
          .attr("transform", function(d, i) {
              return `translate(${barWidth * i + (i + 1) * barMargin}, 0)`;
          });

  // the main visible bar
  bar.append("rect")
      .attr("class", function(d, i) { return "bar series" + i; })
      .attr("width", barWidth)
      // The Y value is the top end of the bar.
      // Negative height values are not allowed.
      .attr("y", function(d) { return yScale(d3.max([d.p, fairValue])); })
      .attr("height", function(d) { return Math.abs(yScale(fairValue) - yScale(d.p)); })
      .append("title")
          .text(function(d) {
            var dp = (100 * (d.p - fairValue) / fairValue);
            if (Math.abs(d.p - fairValue) < 0.001) {
              return `${d.side} is within ${Math.abs(dp).toFixed(1)}% of.`;
            } else if (d.p > fairValue) {
              return `${d.side} is ${dp.toFixed(1)}% more frequent than fair.`;
            } else {
              return `${d.side} is ${-dp.toFixed(1)}% less frequent than fair.`;
            }
          });

  // confidence intervals
  var barCenterX = barWidth / 2;
  bar.append("path")
      .attr("d", function(d) { return "" +
          `M ${barCenterX - 3} ${yScale(d.ci_low)} ` +
          `L ${barCenterX + 3} ${yScale(d.ci_low)} ` +
          `M ${barCenterX} ${yScale(d.ci_low)} ` +
          `L ${barCenterX} ${yScale(d.ci_high)} ` +
          `M ${barCenterX - 3} ${yScale(d.ci_high)} ` +
          `L ${barCenterX + 3} ${yScale(d.ci_high)}`; })
      .attr("class", "ci");

  // legend
  if (srcNames) {
    var legend = chart.append("g")
        .attr("class", "legend")
        .attr(
            "transform",
            `translate(${chartWidth + MARGIN.right}, ${MARGIN.top})`);
    var series = legend.selectAll("g")
        .data(srcNames)
        .enter().append("g")
            .attr("height", barWidth)
            .attr(
                "transform",
                function(d, i) { return `translate(0, ${i * 20})`; });
    series.append("text")
        .text(function(d) { return d; });
    series.append("rect")
        .attr("class", function(d, i) { return "swatch series" + i; })
        .attr("width", barWidth)
        .attr("height", barWidth)
        .attr("x", -(barWidth + 2 * barMargin));
  }

  container.append("text")
      .html("markfickett.com/dice &copy; 2020 cc-by-nc")
      .attr("class", "copyright")
      .attr("x", 20)
      .attr("y", HEIGHT + MARGIN.top + MARGIN.bottom - 15)
      .style("dominant-baseline", "hanging");
}
</%text>
