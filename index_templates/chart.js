<%text>
var margin = {top: 30, right: 30, bottom: 50, left: 50};
var legendWidth = 200;
var height = 300 - (margin.top + margin.bottom);

d3.selectAll('.chart')
    .attr('height', height + 'px');

Object.keys(g_charts).forEach(renderChart);

function renderChart(chartId, i, keys) {
  // Chart container, including space for axes and title.
  var container = d3.select(`#${chartId}`);
  if (container.size() <= 0) {
    console.log(`No chart ${chartId} found in DOM, skipping.`);
    return;
  }

  var chartDetails = g_charts[chartId];
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
  console.log(`Rendering ${title}.`);
  var numSides = srcs[0].length;

  var barMargin = 1;
  var barWidth = 14;
  if (srcs.length > 1) {
    barMargin = 2;
    if (srcs.length <= 4) {
      barWidth = 10;
    } else {
      barWidth = 6;
    }
  }

  var sideGroupWidth = (srcs.length + 3) * barMargin + srcs.length * barWidth;
  var yScale = d3.scaleLinear()
      .range([height, 0]);
  var xScale = d3.scaleBand();

  var xAxis = d3.axisBottom(xScale);
  var yAxis = d3.axisLeft(yScale);

  var chartWidth = numSides * sideGroupWidth;
  var containerWidth = chartWidth + margin.left + margin.right;
  if (srcNames) {
    containerWidth += legendWidth;
  }
  xScale
      .domain(srcs[0].map(function(d) { return d.side; }))
      .range([0, chartWidth]);

  var fairValue = chartDetails.fairValue || 1.0 / numSides;
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
  yScale.domain([0, maxValue]);
  yAxis.tickSizeInner(-chartWidth);

  container
      .attr("width", containerWidth)
      .attr("height", height + margin.top + margin.bottom);
  container.append("text")
      .attr("class", "title")
      .attr("x", (margin.left + chartWidth) / 2)
      .attr("y", 20)
      .style("text-anchor", "middle")
      .text(title);

  var chart = container.append("g")
      .attr("transform", `translate(${margin.left}, ${margin.top})`);

  // Y axis, and dotted line at even probability
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
      .attr("transform", `translate(0, ${height + 1})`)
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
          .attr("height", height)
          .attr("transform", function(d, i) {
              return `translate(${barWidth * i + (i + 1) * barMargin}, 0)`;
          });

  // the main visible bar
  bar.append("rect")
      .attr("class", function(d, i) { return "bar series" + i; })
      .attr("y", function(d) { return yScale(d.p); })
      .attr("width", barWidth)
      .attr("height", function(d) { return height - yScale(d.p); })
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
  var barCenter = barWidth / 2;
  bar.append("path")
      .attr("d", function(d) { return "" +
          `M ${barCenter - 3} ${yScale(d.ci_low)} ` +
          `L ${barCenter + 3} ${yScale(d.ci_low)} ` +
          `M ${barCenter} ${yScale(d.ci_low)} ` +
          `L ${barCenter} ${yScale(d.ci_high)} ` +
          `M ${barCenter - 3} ${yScale(d.ci_high)} ` +
          `L ${barCenter + 3} ${yScale(d.ci_high)}`; })
      .attr("class", "ci");

  // legend
  if (srcNames) {
    var legend = chart.append("g")
        .attr("class", "legend")
        .attr(
            "transform",
            `translate(${chartWidth + margin.right}, ${margin.top})`);
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
      .attr("y", height + margin.top + margin.bottom - 15)
      .style("dominant-baseline", "hanging");
}
</%text>
