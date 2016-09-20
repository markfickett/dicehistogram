var dataLoadRequestsPending = 0;
var loadedData = {};
var charts = {};

var margin = {top: 30, right: 30, bottom: 30, left: 50};
var barMargin = 1;
var barWidth = 18;
var height = 300 - (margin.top + margin.bottom);

d3.selectAll('.chart')
    .attr('height', height + 'px');

d3.json(
    "data-index.json",
    function(error, dataIndex) {
      if (error) {
        console.log('JSON loading error: ' + error);
        return;
      }
      console.log(dataIndex);
      charts = dataIndex.charts;
      dataLoadRequestsPending = dataIndex.srcs.length;
      dataIndex.srcs.forEach(function(d) {
        loadedData[d.filename] = {
            filename: d.filename, name: d.name, data: null};
        d3.csv(
            d.filename + ".csv",
            function(d) {
              d.p = +d.p;
              d.p_5 = +d.p_5;
              d.p_95 = +d.p_95;
              return d;
            },
            function(error, dataSingle) {
              recordAndRenderIfComplete(d.filename, dataSingle);
            });
      });
    });

function recordAndRenderIfComplete(filename, data) {
  console.log(`Loaded ${filename}.`);
  loadedData[filename].data = data;
  dataLoadRequestsPending--;
  if (dataLoadRequestsPending <= 0) {
    console.log("Loading done, ready to render.");
    Object.keys(charts).forEach(renderChart.bind(null, charts));
  }
}

function renderChart(charts, chartId, i, keys) {
  var chartDetails = charts[chartId];
  var srcs = chartDetails.filenames.map(function(filename) {
    return loadedData[filename];
  });
  var title = chartDetails.title;
  if (!title) {
    title = srcs[0].name;
  }
  console.log(`Rendering ${title}.`);
  var numSides = srcs[0].data.length;

  var sideGroupWidth = (srcs.length + 3) * barMargin + srcs.length * barWidth;
  var yScale = d3.scaleLinear()
      .range([height, 0]);
  var xScale = d3.scaleBand();

  var xAxis = d3.axisBottom(xScale);
  var yAxis = d3.axisLeft(yScale);

  var chartWidth = numSides * sideGroupWidth;
  var containerWidth = chartWidth + margin.left + margin.right;
  xScale
      .domain(srcs[0].data.map(function(d) { return d.side; }))
      .range([0, chartWidth]);

  var fairValue = 1.0 / numSides;
  var zippedData = [];
  for(var s = 0; s < numSides; s++) {
    var zippedValue = {side: s + 1, values: []};
    for(var i = 0; i < srcs.length; i++) {
      zippedValue.values.push(srcs[i].data[s]);
    }
    zippedData.push(zippedValue);
  }
  var maxValue = d3.max(srcs, function(src) {
      return d3.max(src.data, function(d) { return d.p_95; })
  });
  yScale.domain([0, maxValue]);
  yAxis.tickSizeInner(-chartWidth);

  var container = d3.select(`#${chartId}`)
      .attr("height", height + margin.top + margin.bottom);
  container.append("text")
      .attr("class", "title")
      .attr("x", containerWidth / 2)
      .attr("y", 20)
      .style("text-anchor", "middle")
      .text(title);

  var chart = container
      .attr("width", containerWidth)
      .append("g")
          .attr("transform", `translate(${margin.left}, ${margin.top})`);

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

  chart.append("g")
      .attr("class", "x axis")
      .attr("transform", `translate(0, ${height + 1})`)
      .call(xAxis)
      .append("text")
          .text("Side")
          .attr("x", chartWidth / 2)
          .attr("y", 29)
          .style("text-andhor", "middle");

  var sideGroup = chart.selectAll("g.side-group")
      .data(zippedData)
      .enter().append("g")
          .attr("class", "side-group")
          .attr("transform", function(d, i) {
              return "translate(" +
                  (xScale(+d.side) + 2 * barMargin) +
                  ", 0)";
          });
  var bar = sideGroup.selectAll("rect")
      .data(function(d, i) { return d.values; })
      .enter().append("g")
          .attr("width", barWidth)
          .attr("height", height)
          .attr("transform", function(d, i) {
              return `translate(${barWidth * i + (i + 1) * barMargin}, 0)`;
          });

  bar.append("rect")
          .attr("y", function(d) { return yScale(d.p); })
          .attr("width", barWidth)
          .attr("height", function(d) { return height - yScale(d.p); });

  var barCenter = barWidth / 2;
  bar.append("path")
      .attr("d", function(d) { console.log(d); return "" +
          `M ${barCenter - 3} ${yScale(d.p_5)} ` +
          `L ${barCenter + 3} ${yScale(d.p_5)} ` +
          `M ${barCenter} ${yScale(d.p_5)} ` +
          `L ${barCenter} ${yScale(d.p_95)} ` +
          `M ${barCenter - 3} ${yScale(d.p_95)} ` +
          `L ${barCenter + 3} ${yScale(d.p_95)}`; })
      .attr("class", "ci");
}
