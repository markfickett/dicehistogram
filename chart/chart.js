var g_dataLoadRequestsPending = d3.set();
var g_loadedData = {};
var g_charts = {};

var margin = {top: 30, right: 100, bottom: 30, left: 50};
var barMargin = 2;
var barWidth = 14;
var height = 300 - (margin.top + margin.bottom);

d3.selectAll('.chart')
    .attr('height', height + 'px');

d3.json(
    "data-index.json",
    function(error, chartsFromJson) {
      if (error) {
        console.log('JSON loading error: ' + error);
        return;
      }
      g_charts = chartsFromJson;
      console.log(g_charts);
      Object.keys(g_charts).forEach(function(chartId) {
        var chartData = g_charts[chartId];
        chartData.filenames.forEach(function(filename) {
          d3.csv(
              filename + ".csv",
              function(d) {
                d.p = +d.p;
                d.p_5 = +d.p_5;
                d.p_95 = +d.p_95;
                return d;
              },
              function(error, dataSingle) {
                recordAndRenderIfComplete(filename, dataSingle);
              }
          );
          g_dataLoadRequestsPending.add(filename);
        });
      });
    });

function recordAndRenderIfComplete(filename, data) {
  console.log(`Loaded ${filename}.`);
  g_loadedData[filename] = data;
  g_dataLoadRequestsPending.remove(filename);
  if (g_dataLoadRequestsPending.empty()) {
    console.log("Loading done, ready to render.");
    Object.keys(g_charts).forEach(renderChart);
  }
}

function renderChart(chartId, i, keys) {
  var chartDetails = g_charts[chartId];
  var srcs = chartDetails.filenames.map(function(filename) {
    return g_loadedData[filename];
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

  var sideGroupWidth = (srcs.length + 3) * barMargin + srcs.length * barWidth;
  var yScale = d3.scaleLinear()
      .range([height, 0]);
  var xScale = d3.scaleBand();

  var xAxis = d3.axisBottom(xScale);
  var yAxis = d3.axisLeft(yScale);

  var chartWidth = numSides * sideGroupWidth;
  var containerWidth = chartWidth + margin.left + margin.right;
  xScale
      .domain(srcs[0].map(function(d) { return d.side; }))
      .range([0, chartWidth]);

  var fairValue = 1.0 / numSides;
  var zippedData = [];
  for(var s = 0; s < numSides; s++) {
    var zippedValue = {side: s + 1, values: []};
    for(var i = 0; i < srcs.length; i++) {
      zippedValue.values.push(srcs[i][s]);
    }
    zippedData.push(zippedValue);
  }
  var maxValue = d3.max(srcs, function(src) {
      return d3.max(src, function(d) { return d.p_95; })
  });
  yScale.domain([0, maxValue]);
  yAxis.tickSizeInner(-chartWidth);

  // Chart container, including space for axes and title.
  var container = d3.select(`#${chartId}`)
      .attr("width", containerWidth)
      .attr("height", height + margin.top + margin.bottom);
  container.append("text")
      .attr("class", "title")
      .attr("x", containerWidth / 2)
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
          .text("Frequency");
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
          .text("Side")
          .attr("x", chartWidth / 2)
          .attr("y", 29)
          .style("text-andhor", "middle");

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
          .attr("y", function(d) { return yScale(d.p); })
          .attr("width", barWidth)
          .attr("height", function(d) { return height - yScale(d.p); });

  // confidence intervals
  var barCenter = barWidth / 2;
  bar.append("path")
      .attr("d", function(d) { return "" +
          `M ${barCenter - 3} ${yScale(d.p_5)} ` +
          `L ${barCenter + 3} ${yScale(d.p_5)} ` +
          `M ${barCenter} ${yScale(d.p_5)} ` +
          `L ${barCenter} ${yScale(d.p_95)} ` +
          `M ${barCenter - 3} ${yScale(d.p_95)} ` +
          `L ${barCenter + 3} ${yScale(d.p_95)}`; })
      .attr("class", "ci");
}
